"""Offline regressions for transport, mapping, validation and service failure paths."""
import sys
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from client import MODELS, RerankError, RerankerClient, normalize_results, validate_request
from service import Runtime, handler_for


def request():
    return {"query": "query", "documents": [{"id": "one", "text": "first"}, {"id": "two", "text": "second"}]}


@pytest.mark.parametrize("value", [None, [], {}, {"query": "", "documents": []},
    {"query": "x", "documents": [{"id": "x", "text": ""}]},
    {"query": "x", "documents": [{"id": "x", "text": "y"}] * 2},
    {"query": "x" * 2001, "documents": [{"id": "x", "text": "y"}]},
    {"query": "x", "documents": [{"id": "x", "text": "y" * 16001}]},
    {"query": "x", "documents": [{"id": str(i), "text": "y"} for i in range(17)]},
    {**request(), "truncate": "true"}, {**request(), "scope": "private"}])
def test_invalid(value):
    with pytest.raises(ValueError):
        validate_request(value)


def test_mapping_and_ties():
    value = request()
    value["documents"][1]["text"] = "first"
    assert validate_request(value) == value
    rows = normalize_results(value["documents"], [{"index": 1, "score": 3}, {"index": 0, "score": 3}])
    assert [row["id"] for row in rows] == ["one", "two"]


@pytest.mark.parametrize("rows", [[], [{"index": 0, "score": 1}] * 2,
    [{"index": 0, "score": float("nan")}, {"index": 1, "score": 1}],
    [{"index": -1, "score": 1}, {"index": 1, "score": 1}],
    [{"index": True, "score": 1}, {"index": 1, "score": 1}]])
def test_bad_backend_mapping(rows):
    with pytest.raises(RerankError):
        normalize_results(request()["documents"], rows)


def test_tei_adapter(monkeypatch):
    client = RerankerClient("gte")
    calls = []
    def transport(path, body=None):
        calls.append((path, body))
        if path == "/info":
            return {"model_id": MODELS["gte"]["model_id"], "model_sha": MODELS["gte"]["revision"]}, {}
        return [{"index": 1, "score": -1}, {"index": 0, "score": 2}], {"x-inference-time": "12"}
    monkeypatch.setattr(client, "_request", transport)
    result = client.rerank(request())
    assert result["inference_ms"] == 12
    assert result["results"][0]["id"] == "one"
    assert calls[1][1]["raw_scores"] is True
    assert calls[1][1]["truncate"] is False
    assert result["truncation"]["status"] == "none"


def test_revision_mismatch(monkeypatch):
    client = RerankerClient("bge")
    monkeypatch.setattr(client, "_request", lambda *args: ({"model_id": MODELS["bge"]["model_id"], "model_sha": "wrong"}, {}))
    with pytest.raises(RerankError, match="revision"):
        client.info()


@pytest.fixture
def running_server():
    servers = []
    def start(handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_port}"
    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_unavailable_and_timeout(running_server, monkeypatch):
    class Slow(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(0.1)
        def log_message(self, *args):
            pass
    client = RerankerClient("gte", running_server(Slow), timeout=0.01)
    with pytest.raises(RerankError, match="timed out"):
        client.ready()
    def refuse(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError())
    monkeypatch.setattr(client.opener, "open", refuse)
    with pytest.raises(RerankError, match="unavailable"):
        client.ready()


def test_startup_failure(monkeypatch, running_server, caplog):
    runtime = Runtime()
    def fail(*args, **kwargs):
        raise OSError("private-token-must-not-escape")
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(set_num_threads=lambda _: None, set_num_interop_threads=lambda _: None))
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=fail))
    monkeypatch.setitem(sys.modules, "mxbai_rerank", SimpleNamespace(MxbaiRerankV2=object))
    runtime.load()
    assert runtime.failed and runtime.model is None
    assert "private-token-must-not-escape" not in caplog.text
    client = RerankerClient("mxbai", running_server(handler_for(runtime)))
    with pytest.raises(RerankError, match="503"):
        client.ready()
    runtime.executor.shutdown()


def test_malformed_mxbai_response(monkeypatch):
    client = RerankerClient("mxbai")
    monkeypatch.setattr(client, "info", lambda: MODELS["mxbai"])
    monkeypatch.setattr(client, "_request", lambda *args: ({"results": []}, {}))
    with pytest.raises(RerankError, match="Malformed backend response"):
        client.rerank(request())


def test_http_validation_and_inference_timeout(running_server, monkeypatch):
    runtime = Runtime()
    runtime.model = object()
    runtime.request_timeout = 0.01
    def slow_score(value):
        try:
            time.sleep(0.15)
            return {"results": []}
        finally:
            runtime.gate.release()
    monkeypatch.setattr(runtime, "score", slow_score)
    client = RerankerClient("mxbai", running_server(handler_for(runtime)))
    with pytest.raises(RerankError, match="400"):
        client._request("/v1/rerank", {})
    with pytest.raises(RerankError, match="504"):
        client._request("/v1/rerank", request())
    with pytest.raises(RerankError, match="429"):
        client._request("/v1/rerank", request())
    runtime.executor.shutdown()
