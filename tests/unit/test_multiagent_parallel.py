"""Unit tests for Milestone 16: Parallel Multi-Agent Execution & Semantic Conflict Detection."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from laew.agent.base import Agent
from laew.agent.executor import AgentExecutor, ExecutionResult
from laew.multiagent.context import SharedContext
from laew.multiagent.coordinator import MultiAgentCoordinator, Conflict
from laew.multiagent.plan import MultiAgentPlan, SubTask
from laew.multiagent.roles import SpecialistRole
from laew.rag.embedding import EmbeddingService


class TestMultiAgentParallel(unittest.TestCase):
    """Test parallel delegation, thread-safe shared context, and semantic conflict detection."""

    def setUp(self) -> None:
        """Set up common test fixtures."""
        # Chief agent (can be None)
        self.chief_agent = Mock(spec=Agent)

        # Specialist agents
        self.specialist_agents = {
            SpecialistRole.ARCHITECT: Mock(spec=Agent),
            SpecialistRole.CODER: Mock(spec=Agent),
            SpecialistRole.REVIEWER: Mock(spec=Agent),
        }

        # Shared context
        self.shared_context = SharedContext()

        # Coordinator
        self.coordinator = MultiAgentCoordinator(
            chief=self.chief_agent,
            agents=self.specialist_agents,
        )

        # Sample plan with three subtasks
        self.plan = MultiAgentPlan(
            name="test-plan",
            objective="Test objective",
            subtasks=[
                SubTask(
                    id="task1",
                    prompt="First subtask",
                    role=SpecialistRole.ARCHITECT,
                    deliverable="output1",
                ),
                SubTask(
                    id="task2",
                    prompt="Second subtask",
                    role=SpecialistRole.CODER,
                    deliverable="output2",
                ),
                SubTask(
                    id="task3",
                    prompt="Third subtask",
                    role=SpecialistRole.REVIEWER,
                    deliverable="output1",  # Same deliverable as task1 to test conflict detection
                ),
            ],
            synthesize=True,
        )

    def _mock_executor_success(self, output: str) -> Mock:
        """Create a mock AgentExecutor that returns a successful ExecutionResult."""
        mock_executor = Mock(spec=AgentExecutor)
        mock_executor.run.return_value = ExecutionResult(
            agent_name="test-agent",
            success=True,
            final_response=output,
            error="",
        )
        return mock_executor

    def _mock_executor_failure(self, error_msg: str) -> Mock:
        """Create a mock AgentExecutor that returns a failed ExecutionResult."""
        mock_executor = Mock(spec=AgentExecutor)
        mock_executor.run.return_value = ExecutionResult(
            agent_name="test-agent",
            success=False,
            final_response="",
            error=error_msg,
        )
        return mock_executor

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_parallel_delegation_order_preserved(self, mock_executor_class: Mock) -> None:
        """Test that parallel delegation preserves subtask order in results."""
        # Configure mock executor to return different outputs per subtask
        def executor_side_effect(agent: Agent) -> Mock:
            # Get the role from the agent (we'll need to map agents back to roles for this test)
            # For simplicity, we'll return different outputs based on which agent we got
            if agent == self.specialist_agents[SpecialistRole.ARCHITECT]:
                output = "output from Architect"
            elif agent == self.specialist_agents[SpecialistRole.CODER]:
                output = "output from Coder"
            else:  # REVIEWER
                output = "output from Reviewer"

            mock_executor = self._mock_executor_success(output)
            return mock_executor

        mock_executor_class.side_effect = executor_side_effect

        # Run plan in parallel
        result = self.coordinator.run(self.plan, parallel=True)

        # Check that we have three delegations in the correct order
        self.assertEqual(len(result.delegations), 3)
        self.assertEqual(result.delegations[0].role, SpecialistRole.ARCHITECT)
        self.assertEqual(result.delegations[0].output, "output from Architect")
        self.assertEqual(result.delegations[1].role, SpecialistRole.CODER)
        self.assertEqual(result.delegations[1].output, "output from Coder")
        self.assertEqual(result.delegations[2].role, SpecialistRole.REVIEWER)
        self.assertEqual(result.delegations[2].output, "output from Reviewer")

        # Check that the shared context contains the outputs
        self.assertEqual(result.context.get("output1").content, "output from Reviewer")  # Last writer wins
        self.assertEqual(result.context.get("output2").content, "output from Coder")

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_shared_context_thread_safety(self, mock_executor_class: Mock) -> None:
        """Test that shared context is thread-safe under concurrent read/write."""
        # Configure mock executor to post to shared context and then read from it
        def executor_side_effect(agent: Agent) -> Mock:
            mock_executor = self._mock_executor_success("agent output")
            return mock_executor

        mock_executor_class.side_effect = executor_side_effect

        # Create a plan with many subtasks to increase chance of race conditions
        many_subtasks = [
            SubTask(
                id=f"task{i}",
                prompt=f"Task {i}",
                role=SpecialistRole.ARCHITECT,  # All same role for simplicity
                deliverable=f"key{i % 5}",  # Cycle through 5 keys
            )
            for i in range(20)
        ]
        plan = MultiAgentPlan(name="concurrency-test", objective="Concurrency test", subtasks=many_subtasks)

        # Run in parallel with multiple workers
        result = self.coordinator.run(plan, parallel=True, max_workers=5)

        # Check that all delegations succeeded
        self.assertTrue(all(d.success for d in result.delegations))
        self.assertEqual(len(result.delegations), 20)

        # Verify that each key in the shared context has the expected number of entries
        for i in range(5):
            key = f"key{i}"
            entries = result.context.all_for(key)
            # Each key should have been posted to 4 times (20 tasks / 5 keys)
            self.assertEqual(len(entries), 4, f"Key {key} should have 4 entries")

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_semantic_conflict_detection_matching_semantics(self, mock_executor_class: Mock) -> None:
        """Test that semantically similar outputs do not trigger conflicts."""
        # Configure mock executor to return semantically similar outputs
        def executor_side_effect(agent: Agent) -> Mock:
            # All agents return outputs that are semantically similar (e.g., paraphrases)
            mock_executor = self._mock_executor_success("The quick brown fox jumps over the lazy dog")
            return mock_executor

        mock_executor_class.side_effect = executor_side_effect

        # Create a mock embedding service that returns similar vectors
        mock_embedding_service = Mock(spec=EmbeddingService)
        # Return vectors that are identical (cosine similarity = 1.0)
        mock_embedding_service.embed_batch.return_value = [[0.5, 0.5], [0.5, 0.5]]

        # Run plan with semantic conflict detection
        result = self.coordinator.run(
            self.plan,
            parallel=False,  # Sequential for simplicity in this test
            embedding_service=mock_embedding_service,
            conflict_threshold=0.85,
        )

        # Check that no conflicts were detected
        self.assertEqual(len(result.conflicts), 0)

        # Verify that embeddings were called for the deliverable with multiple outputs ("output1" has 2 outputs)
        self.assertEqual(mock_embedding_service.embed_batch.call_count, 1)

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_semantic_conflict_detection_semantic_divergence(self, mock_executor_class: Mock) -> None:
        """Test that semantically divergent outputs trigger conflicts."""
        # Configure mock executor to return divergent outputs
        outputs = [
            "The quick brown fox jumps over the lazy dog",  # Task 1 (Architect)
            "A fast brown fox leaps above a sleepy canine",  # Task 2 (Coder) - similar
            "The patient wolf was not bothered by the pink fox",  # Task 3 (Reviewer) - divergent
        ]

        def executor_side_effect(agent: Agent) -> Mock:
            # Return outputs in order of subtasks
            if agent == self.specialist_agents[SpecialistRole.ARCHITECT]:
                mock_executor = self._mock_executor_success(outputs[0])
            elif agent == self.specialist_agents[SpecialistRole.CODER]:
                mock_executor = self._mock_executor_success(outputs[1])
            else:  # REVIEWER
                mock_executor = self._mock_executor_success(outputs[2])
            return mock_executor

        mock_executor_class.side_effect = executor_side_effect

        # Create a mock embedding service that returns vectors with known similarities
        mock_embedding_service = Mock(spec=EmbeddingService)
        # Vectors: [fox_sentence, similar_sentence, divergent_sentence]
        # We'll set up similarities:
        #   fox_sentence vs similar_sentence: 0.9 (above threshold)
        #   fox_sentence vs divergent_sentence: 0.7 (below threshold)
        #   similar_sentence vs divergent_sentence: 0.6 (below threshold)
        mock_embedding_service.embed_batch.return_value = [
            [1.0, 0.0],  # fox_sentence
            [0.9, 0.1],  # similar_sentence (cosine similarity with first: ~0.9)
            [0.6, 0.8],  # divergent_sentence (cosine similarity with first: ~0.6)
        ]

        # Run plan with semantic conflict detection
        result = self.coordinator.run(
            self.plan,
            parallel=False,
            embedding_service=mock_embedding_service,
            conflict_threshold=0.85,
        )

        # Check that conflicts were detected (at least one conflict due to divergence)
        self.assertGreater(len(result.conflicts), 0)
        # The conflict should be on deliverable "output1" (shared by task1 and task3)
        conflict_deliverables = {c.deliverable for c in result.conflicts}
        self.assertIn("output1", conflict_deliverables)

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_fallback_to_text_normalization_on_embedding_error(self, mock_executor_class: Mock) -> None:
        """Test that conflict detection falls back to text normalization when embedding service fails."""
        # Configure mock executor to return outputs that are textually different but would be similar after normalization
        outputs = [
            "Hello World",  # Task 1 (Architect)
            "hello   world",  # Task 2 (Coder) - same after normalization
            "HELLO WORLD",  # Task 3 (Reviewer) - same after normalization
        ]

        def executor_side_effect(agent: Agent) -> Mock:
            # Return outputs in order of subtasks
            if agent == self.specialist_agents[SpecialistRole.ARCHITECT]:
                mock_executor = self._mock_executor_success(outputs[0])
            elif agent == self.specialist_agents[SpecialistRole.CODER]:
                mock_executor = self._mock_executor_success(outputs[1])
            else:  # REVIEWER
                mock_executor = self._mock_executor_success(outputs[2])
            return mock_executor

        mock_executor_class.side_effect = executor_side_effect

        # Create a mock embedding service that raises an exception
        mock_embedding_service = Mock(spec=EmbeddingService)
        mock_embedding_service.embed_batch.side_effect = RuntimeError("Embedding service unavailable")

        # Run plan with semantic conflict detection (should fall back to text normalization)
        result = self.coordinator.run(
            self.plan,
            parallel=False,
            embedding_service=mock_embedding_service,
            conflict_threshold=0.85,
        )

        # Check that no conflicts were detected (because outputs normalize to same text)
        self.assertEqual(len(result.conflicts), 0)

        # Verify that the embedding service was called and then fell back
        self.assertTrue(mock_embedding_service.embed_batch.called)

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_parallel_execution_with_failures(self, mock_executor_class: Mock) -> None:
        """Test that parallel execution handles specialist failures gracefully."""
        # Configure mock executor to fail for the second subtask (CODER)
        def executor_side_effect(agent: Agent) -> Mock:
            if agent == self.specialist_agents[SpecialistRole.CODER]:
                return self._mock_executor_failure("Specialist failed")
            return self._mock_executor_success("Success")

        mock_executor_class.side_effect = executor_side_effect

        # Run plan in parallel
        result = self.coordinator.run(self.plan, parallel=True)

        # Check that we have three delegations
        self.assertEqual(len(result.delegations), 3)
        # Check that the second delegation (CODER) failed
        self.assertEqual(result.delegations[1].role, SpecialistRole.CODER)
        self.assertFalse(result.delegations[1].success)
        self.assertEqual(result.delegations[1].error, "Specialist failed")
        # Check that the other delegations succeeded
        self.assertEqual(result.delegations[0].role, SpecialistRole.ARCHITECT)
        self.assertTrue(result.delegations[0].success)
        self.assertEqual(result.delegations[2].role, SpecialistRole.REVIEWER)
        self.assertTrue(result.delegations[2].success)

    def test_cosine_similarity_helper(self) -> None:
        """Test the cosine similarity helper function."""
        from laew.multiagent.coordinator import _cosine_similarity

        # Test identical vectors
        self.assertAlmostEqual(_cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        # Test orthogonal vectors
        self.assertAlmostEqual(_cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)
        # Test opposite vectors
        self.assertAlmostEqual(_cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)
        # Test zero vector
        self.assertEqual(_cosine_similarity([0.0, 0.0], [1.0, 0.0]), 0.0)
        self.assertEqual(_cosine_similarity([1.0, 0.0], [0.0, 0.0]), 0.0)


if __name__ == "__main__":
    unittest.main()