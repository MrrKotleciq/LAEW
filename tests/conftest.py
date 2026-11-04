"""Shared test-suite configuration for LAEW."""

import pytest


@pytest.fixture(autouse=True)
def offline_service_boundary(monkeypatch, request):
    """Offline tests cannot reach production services or start their scheduler."""
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setenv('LAEW_MEMORY_STORAGE',str(request.config._tmp_path_factory.mktemp('memory')/'memory.db'))
    monkeypatch.setenv('LAEW_KNOWLEDGE_STORAGE',str(request.config._tmp_path_factory.mktemp('knowledge')/'curation.db'))
    from laew.knowledge.integration import KnowledgeWorker
    monkeypatch.setattr(KnowledgeWorker,'start',lambda self: None)
    from laew.memory.integration import MemoryWorker
    monkeypatch.setattr(MemoryWorker,'start',lambda self: None)
    import socket
    from pathlib import Path
    from laew.rag.sync import SyncScheduler
    original_connect = socket.socket.connect
    original_start = SyncScheduler.start

    def connect(sock, address):
        if isinstance(address, tuple):
            host, port = address[:2]
            if host not in {"127.0.0.1", "::1", "localhost"} or port < 10000 or port == 11434:
                raise OSError("Offline tests cannot connect to production/external services.")
        return original_connect(sock, address)

    def start(scheduler, root=None):
        test_root = request.config._tmp_path_factory.getbasetemp()
        if root is None or not Path(root).resolve().is_relative_to(test_root):
            raise AssertionError("Offline tests cannot start a production scheduler.")
        return original_start(scheduler, root)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(SyncScheduler, "start", start)


@pytest.fixture
def llamacpp_server():
    """A configurable, always-available llama.cpp OpenAI-compatible server.

    Starts the in-process :class:`LlamaCppTestServer` on an ephemeral port in a
    daemon thread, yielding ``(base_url, server)``.  ``base_url`` already ends in
    ``/v1``.  The server is stdlib-only (no external dependency, no
    ``llama-server`` binary, no ``.gguf`` weights), so these integration tests
    run rather than skip.
    """
    from .integration._llamacpp_test_server import LlamaCppTestServer

    server = LlamaCppTestServer()
    base = server.start()
    yield base, server
    server.stop()
