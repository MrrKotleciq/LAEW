"""Controlled multi-turn adapter evaluation; this does not score model answers."""
from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.knowledge.routing import KnowledgeTurn
from laew.memory.service import MemoryService
from laew.memory.store import MemoryStore
from laew.security.permissions import PermissionBroker
from test_knowledge_routing import ObservingProvider, isolated_runtime  # noqa: F401


def test_conversation_evidence_and_routing_metrics(isolated_runtime, tmp_path):
    rag = isolated_runtime.build(isolated_runtime.active)
    store = MemoryStore(tmp_path / "conversation.db")
    store.save_settings({"semantic_enabled": False})
    store.remember("Użytkownik chciałby odwiedzić Kioto.")
    memory = MemoryService(store)
    provider = ObservingProvider("Controlled response; no answer quality is inferred.")
    executor = AgentExecutor(Agent(AgentConfig(), provider=provider, tools=[rag]))
    broker = PermissionBroker(isolated_runtime.active)
    class FixtureAssessor:
        def assess(self, question, memories):
            return {"status": "completed", "sufficient": True, "calls": 1, "elapsed_ms": 0}
    turn = KnowledgeTurn(lambda tool, op, args: broker.call(tool, op, args, None), assessor=FixtureAssessor())
    # Required source and marker describe the evidence needed in the adapter,
    # not a judgment of the fixed provider reply.
    cases = [
        ("Jakie miasto chciałbym odwiedzić?", "memory", "Kioto", False),
        ("A co jeszcze?", "global", "GLOBAL-7319", True),
        ("Wyjaśnij architekturę PermissionBroker w aktualnym projekcie.", "project", "PROJECT-4281", False),
        ("Sprawdz dokladniej.", "project", "PROJECT-4281", True),
        ("Cześć", None, None, False),
        ("Jakie miasto chciałbym odwiedzić?", "memory", "Kioto", False),
    ]
    required = found = covered = unnecessary = 0
    memory_reads = rag_reads = escalations = empty = 0
    retrieval_ms = context_tokens = 0
    for message, source, marker, bound in cases:
        turn.prepare(executor, message, "active", lambda: memory, rag)
        assert executor.run(message, on_tool_call=turn.call, on_diagnostic=turn.observe).success
        diag = turn.diagnostics
        assert diag["topic_from_history"] is bound
        invoked = {s["scope"] for s in diag["prefetch"] if s.get("search_executed")}
        if diag["memory_recall"].get("invoked"):
            invoked.add("memory")
        memory_reads += int(diag["memory_recall"].get("invoked", False))
        rag_reads += sum(bool(s.get("search_executed")) for s in diag["prefetch"])
        escalations += int("escalation" in diag)
        empty += sum(s.get("status") == "empty" for s in diag["prefetch"])
        retrieval_ms += diag["memory_recall"].get("elapsed_ms", 0)
        retrieval_ms += sum(s.get("elapsed_ms", 0) for s in diag["prefetch"])
        context_tokens += diag["memory_recall"].get("estimated_context_size", 0)
        context_tokens += sum(s.get("estimated_context_size", 0) for s in diag["prefetch"])
        if message == cases[0][0]:
            assert diag["assessment"]["status"] == "sufficient"
            assert "escalation" not in diag
        if source:
            required += 1
            found += source in invoked
            covered += marker in provider.messages[-1][0].content
        else:
            unnecessary += bool(invoked)
        assert "PRIVATE-9999" not in provider.messages[-1][0].content
    print(f"required_source_recall={found}/{required} evidence_coverage={covered}/{required} "
          f"unnecessary_retrieval={unnecessary}/1 memory_reads={memory_reads} rag_reads={rag_reads} "
          f"escalations={escalations} empty_rag={empty} retrieval_ms={retrieval_ms:.1f} "
          f"estimated_context_tokens={context_tokens}")
    assert (found, covered, unnecessary) == (required, required, 0)
