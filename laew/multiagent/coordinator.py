"""Chief agent coordination runtime for LAEW multi-agent delegation.

Implements the multi-agent orchestration loop: the chief agent registers
specialist agents, delegates subtasks to them in isolation, collects results,
detects conflicts between specialists, and (optionally) synthesizes a final
answer (ADR-018). Specialist failures are isolated so they do not abort the
entire run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import threading
import concurrent.futures
import math

from laew.agent.base import Agent
from laew.agent.executor import AgentExecutor, ExecutionResult
from laew.multiagent.context import SharedContext
from laew.multiagent.message import AgentMessage, MessageKind
from laew.multiagent.plan import MultiAgentPlan, SubTask
from laew.multiagent.roles import SpecialistRole
from laew.rag.embedding import EmbeddingService


@dataclass(frozen=True)
class DelegationResult:
    """Outcome of delegating a single subtask to a specialist agent.

    Attributes:
        role: The specialist role that performed the work.
        subtask_id: The identifier of the subtask from the plan.
        deliverable: The deliverable key shared via context (matches
            ``SubTask.deliverable``). Used to detect conflicts.
        success: True if the agent returned a non-error result.
        output: The agent's final response text when successful.
        error: Error message when the delegation failed.
        message: The raw AgentMessage that carried the result (if any).
    """

    role: SpecialistRole
    subtask_id: str
    deliverable: str
    success: bool
    output: str = ""
    error: str = ""
    message: Optional[AgentMessage] = None


@dataclass(frozen=True)
class Conflict:
    """A disagreement between two or more specialists on the same deliverable.

    Attributes:
        deliverable: The context key being contested.
        agents: The specialist roles that produced conflicting outputs.
        outputs: The conflicting output strings, indexed by role.
    """

    deliverable: str
    agents: List[SpecialistRole]
    outputs: Dict[SpecialistRole, str]


@dataclass
class MultiAgentResult:
    """Aggregated outcome of a multi-agent plan run.

    Attributes:
        success: True if the chief agent synthesized a final response.
        delegations: List of per-subtask delegation outcomes.
        conflicts: Detected disagreements between specialists.
        final_response: The chief agent's synthesized answer (if any).
        error: Error message when the run failed before synthesis.
        context: The shared context journal populated during the run.
    """

    success: bool = False
    delegations: List[DelegationResult] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    final_response: str = ""
    error: str = ""
    context: SharedContext = field(default_factory=SharedContext)


def _normalize_text(text: str) -> str:
    """Return a normalized version of text for conflict detection.

    Normalization steps:
    - Strip leading/trailing whitespace.
    - Collapse consecutive whitespace (including newlines) to a single space.
    - Lowercase the result.
    """
    import re

    return re.sub(r"\s+", " ", text.strip().lower())


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


class MultiAgentCoordinator:
    """Chief agent that orchestrates specialist agents per a MultiAgentPlan.

    The coordinator does not perform any substantive work itself; it:
    1. Holds references to the chief agent (optional) and specialist agents.
    2. For each subtask, builds a prompt that includes the shared context
       accumulated so far and delegates to the appropriate specialist.
    3. Records each specialist's output (or failure) in the shared context.
    4. After all subtasks, compares outputs for the same deliverable to
       detect conflicts.
    5. If synthesis is requested, asks the chief agent to produce a final
       answer from the accumulated shared context.

    Specialist agents are invoked in isolation: each delegation uses a fresh
    AgentExecutor so that tool approvals, history, and model state do not leak
    between delegations (failure isolation, principle P8).
    """

    def __init__(
        self,
        chief: Optional[Agent],
        agents: Dict[SpecialistRole, Agent],
    ) -> None:
        self.chief = chief
        self.agents = agents
        self._delegations: List[DelegationResult] = []

    # --------------------------------------------------------------------- #
    # Delegation helpers
    # --------------------------------------------------------------------- #
    def _build_delegation_prompt(
        self,
        subtask: SubTask,
        shared_context: SharedContext,
    ) -> str:
        """Assemble the prompt for a specialist agent.

        The prompt consists of:
        1. The subtask's natural-language instruction.
        2. A blank line.
        3. The rendered shared context (if any).
        """
        parts = [subtask.prompt.strip()]
        context_render = shared_context.render()
        if context_render:
            parts.append("")
            parts.append(context_render)
        return "\n".join(parts)

    def _delegate_subtask(
        self,
        subtask: SubTask,
        shared_context: SharedContext,
    ) -> DelegationResult:
        """Delegate a single subtask to its specialist agent in isolation.

        Returns a DelegationResult capturing success/failure and any output.
        """
        agent = self.agents[subtask.role]
        executor = AgentExecutor(agent)

        prompt = self._build_delegation_prompt(subtask, shared_context)
        result: ExecutionResult = executor.run(prompt)

        if result.success:
            output = result.final_response.strip()
            # Record the successful output in the shared context so later
            # specialists can see it (principle P2, shared knowledge).
            shared_context.post(
                key=subtask.deliverable,
                content=output,
                source=subtask.role.value,
            )
            msg = AgentMessage(
                kind=MessageKind.RESULT,
                content=output,
                sender=subtask.role.value,
                recipient="chief",
                correlation_id=subtask.id,
                metadata={"deliverable": subtask.deliverable},
            )
            return DelegationResult(
                role=subtask.role,
                subtask_id=subtask.id,
                deliverable=subtask.deliverable,
                success=True,
                output=output,
                message=msg,
            )
        else:
            error_msg = result.error or "Unknown error"
            # Record the failure as well so the chief knows something went wrong.
            shared_context.post(
                key=f"{subtask.deliverable}:error",
                content=error_msg,
                source=subtask.role.value,
            )
            msg = AgentMessage(
                kind=MessageKind.ERROR,
                content=error_msg,
                sender=subtask.role.value,
                recipient="chief",
                correlation_id=subtask.id,
                metadata={"deliverable": subtask.deliverable},
            )
            return DelegationResult(
                role=subtask.role,
                subtask_id=subtask.id,
                deliverable=subtask.deliverable,
                success=False,
                error=error_msg,
                message=msg,
            )

    # --------------------------------------------------------------------- #
    # Conflict detection
    # --------------------------------------------------------------------- #
    def _detect_conflicts_text(
        self,
        shared_context: SharedContext,
        plan: MultiAgentPlan,
    ) -> List[Conflict]:
        """Compare specialist outputs for the same deliverable using text normalization.

        Returns a list of Conflict objects where two or more specialists
        produced materially different outputs for the same deliverable key.
        """
        conflicts: List[Conflict] = []

        # Group results by deliverable key
        by_deliverable: Dict[str, Dict[SpecialistRole, str]] = {}
        for delegation in self._delegations:
            if not delegation.success:
                continue
            d = delegation.deliverable
            by_deliverable.setdefault(d, {})[delegation.role] = delegation.output

        for deliverable, outputs in by_deliverable.items():
            if len(outputs) < 2:
                continue  # need at least two to conflict

            # Normalize outputs for comparison
            normalized: Dict[SpecialistRole, str] = {
                role: _normalize_text(text) for role, text in outputs.items()
            }
            unique_normalized = set(normalized.values())

            if len(unique_normalized) <= 1:
                continue  # all outputs are effectively identical

            # Build conflict report
            agents = list(outputs.keys())
            conflicts.append(
                Conflict(
                    deliverable=deliverable,
                    agents=agents,
                    outputs={role: outputs[role] for role in agents},
                )
            )

        return conflicts

    def _detect_conflicts_semantic(
        self,
        shared_context: SharedContext,
        plan: MultiAgentPlan,
        embedding_service: EmbeddingService,
        conflict_threshold: float = 0.85,
    ) -> List[Conflict]:
        """Compare specialist outputs for the same deliverable using semantic similarity.

        Returns a list of Conflict objects where two or more specialists
        produced materially different outputs for the same deliverable key.
        Falls back to text normalization if embedding service fails.
        """
        conflicts: List[Conflict] = []

        # Group results by deliverable key
        by_deliverable: Dict[str, Dict[SpecialistRole, str]] = {}
        for delegation in self._delegations:
            if not delegation.success:
                continue
            d = delegation.deliverable
            by_deliverable.setdefault(d, {})[delegation.role] = delegation.output

        for deliverable, outputs in by_deliverable.items():
            if len(outputs) < 2:
                continue  # need at least two to conflict

            # Try semantic comparison first
            try:
                # Get embeddings for all outputs
                texts = list(outputs.values())
                embeddings = embedding_service.embed_batch(texts)

                # Check if all pairs are above threshold (semantically similar)
                all_similar = True
                for i in range(len(embeddings)):
                    for j in range(i + 1, len(embeddings)):
                        similarity = _cosine_similarity(embeddings[i], embeddings[j])
                        if similarity < conflict_threshold:
                            all_similar = False
                            break
                    if not all_similar:
                        break

                if all_similar:
                    continue  # all outputs are semantically similar

            except (ValueError, KeyError, TypeError, RuntimeError):
                # Fall back to text normalization if embedding fails
                pass

            # Fallback to text normalization
            normalized: Dict[SpecialistRole, str] = {
                role: _normalize_text(text) for role, text in outputs.items()
            }
            unique_normalized = set(normalized.values())

            if len(unique_normalized) <= 1:
                continue  # all outputs are effectively identical

            # Build conflict report
            agents = list(outputs.keys())
            conflicts.append(
                Conflict(
                    deliverable=deliverable,
                    agents=agents,
                    outputs={role: outputs[role] for role in agents},
                )
            )

        return conflicts

    # --------------------------------------------------------------------- #
    # Chief synthesis
    # --------------------------------------------------------------------- #
    def _synthesize_final_answer(
        self,
        shared_context: SharedContext,
        plan: MultiAgentPlan,
    ) -> str:
        """Ask the chief agent to synthesize a final answer from the context.

        Returns the chief's response (empty string if chief is None or fails).
        """
        if self.chief is None:
            return ""

        executor = AgentExecutor(self.chief)
        prompt = (
            "You are the chief agent. Synthesize the work of the specialist "
            "agents into a single coherent answer that satisfies the overall "
            f'objective: "{plan.objective}".\n\n'
            "Ground every statement in the accumulated context. If a "
            "specialist failed, report the failure exactly as described and "
            "do NOT invent a cause for it. Label any interpretation as "
            "INFERENCE — never present an inference or hypothesis as a fact.\n\n"
            + shared_context.render("Accumulated context from specialists:")
        )
        result = executor.run(prompt)
        return result.final_response.strip() if result.success else ""

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def run(
        self,
        plan: MultiAgentPlan,
        *,
        parallel: bool = False,
        max_workers: Optional[int] = None,
        embedding_service: Optional[EmbeddingService] = None,
        conflict_threshold: float = 0.85,
    ) -> MultiAgentResult:
        """Execute the multi-agent plan and return the aggregated result.

        Steps:
        1. Reset shared context.
        2. For each subtask in order:
           a. Delegate to the appropriate specialist (isolated executor).
           b. Record outcome.
           c. On success, post output to shared context.
        3. Detect conflicts between specialists.
        4. If synthesis requested, ask the chief agent for a final answer.
        5. Return the populated MultiAgentResult.

        Args:
            plan: The multi-agent plan to execute.
            parallel: If True, execute subtasks concurrently using a thread pool.
            max_workers: Maximum number of workers in the thread pool (defaults to number of subtasks).
            embedding_service: Optional embedding service for semantic conflict detection.
            conflict_threshold: Cosine similarity threshold for semantic conflict detection (0.0-1.0).
                               Higher values mean stricter similarity requirements.
        """
        # Reset context for a clean run
        context = SharedContext()
        self._delegations = []

        # 1. Delegate each subtask to its specialist
        if parallel and len(plan.subtasks) > 1:
            # Parallel execution with ThreadPoolExecutor
            # Determine number of workers
            if max_workers is None:
                max_workers = len(plan.subtasks)
            else:
                max_workers = min(max_workers, len(plan.subtasks))

            # Use ThreadPoolExecutor for concurrent delegation
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all delegation tasks
                future_to_subtask = {
                    executor.submit(self._delegate_subtask, subtask, context): subtask
                    for subtask in plan.subtasks
                }

                # Collect results as they complete, maintaining order
                delegations: List[Optional[DelegationResult]] = [None] * len(plan.subtasks)
                for future in concurrent.futures.as_completed(future_to_subtask):
                    subtask = future_to_subtask[future]
                    try:
                        delegation_result = future.result()
                        # Find the index of this subtask to maintain order
                        idx = plan.subtasks.index(subtask)
                        delegations[idx] = delegation_result
                    except Exception as exc:
                        # Handle unexpected errors in delegation
                        error_msg = f"Delegation failed with exception: {exc}"
                        context.post(
                            key=f"{subtask.deliverable}:error",
                            content=error_msg,
                            source=subtask.role.value,
                        )
                        msg = AgentMessage(
                            kind=MessageKind.ERROR,
                            content=error_msg,
                            sender=subtask.role.value,
                            recipient="chief",
                            correlation_id=subtask.id,
                            metadata={"deliverable": subtask.deliverable},
                        )
                        delegation_result = DelegationResult(
                            role=subtask.role,
                            subtask_id=subtask.id,
                            deliverable=subtask.deliverable,
                            success=False,
                            error=error_msg,
                            message=msg,
                        )
                        idx = plan.subtasks.index(subtask)
                        delegations[idx] = delegation_result

                # Filter out None values (shouldn't happen, but just in case)
                self._delegations = [d for d in delegations if d is not None]
        else:
            # Sequential execution (original behavior)
            for subtask in plan.subtasks:
                delegation_result = self._delegate_subtask(subtask, context)
                self._delegations.append(delegation_result)

        # 2. Detect conflicts
        conflicts: List[Conflict] = []
        if embedding_service is not None:
            # Use semantic conflict detection
            conflicts = self._detect_conflicts_semantic(
                context, plan, embedding_service, conflict_threshold
            )
        else:
            # Fall back to text-based conflict detection
            conflicts = self._detect_conflicts_text(context, plan)

        # 3. Optional synthesis by the chief
        final_response = ""
        if plan.synthesize and self.chief is not None:
            final_response = self._synthesize_final_answer(context, plan)

        # Determine overall success: at least one delegation succeeded and we have
        # a final response when synthesis was requested.
        any_success = any(d.success for d in self._delegations)
        synthesis_ok = (not plan.synthesize) or bool(final_response)
        overall_success = any_success and synthesis_ok

        error_msg = ""
        if not any_success:
            error_msg = "All specialist delegations failed"
        elif plan.synthesize and not final_response:
            error_msg = "Chief agent failed to synthesize a final response"

        return MultiAgentResult(
            success=overall_success,
            delegations=list(self._delegations),
            conflicts=conflicts,
            final_response=final_response,
            error=error_msg,
            context=context,
        )