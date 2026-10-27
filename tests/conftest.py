"""Shared test-suite configuration for LAEW."""

import pytest


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
