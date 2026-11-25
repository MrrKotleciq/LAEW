"""Shared test-suite configuration for LAEW."""

import os
from pathlib import Path
import tempfile

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    base = config.getoption("basetemp")
    if base and os.path.lexists(base):
        raise pytest.UsageError("--basetemp must name a new directory")
    temporary_parent = Path(base or os.environ.get("PYTEST_DEBUG_TEMPROOT") or tempfile.gettempdir()).resolve()
    if temporary_parent.is_relative_to(Path(__file__).resolve().parents[1]):
        raise pytest.UsageError('pytest temporary storage must be outside the repository')
    if os.name == 'nt' and temporary_parent.is_relative_to(Path(r'C:\ROOT').resolve()):
        raise pytest.UsageError('pytest temporary storage must be outside C:\\ROOT')
    if any((path / '.obsidian').is_dir() for path in (temporary_parent, *temporary_parent.parents)):
        raise pytest.UsageError('pytest temporary storage must be outside Obsidian vaults')
    if base:
        # pytest replaces its basetemp if it exists. Reserve a fresh parent
        # atomically and pass pytest a child that only this run can claim.
        try:
            temporary_parent.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise pytest.UsageError("--basetemp must name a new directory") from exc
        except OSError as exc:
            raise pytest.UsageError(f"Cannot create --basetemp: {exc}") from exc
        config.option.basetemp = str(temporary_parent / "fixtures")


@pytest.fixture(autouse=True)
def offline_service_boundary(monkeypatch, request, tmp_path_factory):
    """Confine test storage and keep offline tests away from deployed services."""
    test_root = tmp_path_factory.getbasetemp()
    # A unique directory for each test is inherited by subprocesses and removed
    # even when the test fails. Never use a caller-supplied storage override.
    with tempfile.TemporaryDirectory(prefix="laew-storage-", dir=test_root) as storage:
        for name in ("TEMP", "TMP", "TMPDIR"):
            monkeypatch.setenv(name, storage)
        monkeypatch.setattr(tempfile, "tempdir", storage)
        monkeypatch.setenv('LAEW_MEMORY_STORAGE', str(Path(storage) / 'memory.db'))
        monkeypatch.setenv('LAEW_KNOWLEDGE_STORAGE', str(Path(storage) / 'curation.db'))
        monkeypatch.setenv("LAEW_WORKSPACE_ROOT", storage)
        monkeypatch.delenv("LAEW_INSTALLATION_FENCE", raising=False)
        monkeypatch.delenv("LAEW_PROTECTED_PROFILE", raising=False)
        _confine_stores(monkeypatch, test_root)
        if not request.node.get_closest_marker("live"):
            _block_operational_services(monkeypatch, test_root)
        yield


def _confine_stores(monkeypatch, test_root):
    # Reject accidental use of explicit production paths as well as defaults.
    # Tests that exercise path resolution without opening a store remain free
    # to inspect any path. This applies to explicitly opted-in live tests too.
    from laew.console.session_store import SessionStore
    from laew.knowledge.store import KnowledgeStore
    from laew.memory.store import MemoryStore

    for store_type, parameter in ((SessionStore, "directory"), (KnowledgeStore, "path"), (MemoryStore, "path")):
        original_init = store_type.__init__

        def guarded_init(self, *args, _init=original_init, _parameter=parameter, **kwargs):
            path = args[0] if args else kwargs.get(_parameter)
            if path is not None and not Path(path).resolve().is_relative_to(test_root):
                raise AssertionError("Test storage must be inside pytest temporary storage")
            _init(self, *args, **kwargs)

        monkeypatch.setattr(store_type, '__init__', guarded_init)


def _block_operational_services(monkeypatch, test_root):
    from laew.knowledge.integration import KnowledgeWorker
    monkeypatch.setattr(KnowledgeWorker,'start',lambda self: None)
    from laew.memory.integration import MemoryWorker
    monkeypatch.setattr(MemoryWorker,'start',lambda self: None)
    import socket
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
