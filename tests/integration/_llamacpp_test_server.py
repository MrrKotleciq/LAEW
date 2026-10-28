"""Lightweight in-process HTTP server for llama.cpp OpenAI-compatible routes.

Implements three routes so the llama.cpp integration tests can drive the **real**
HTTP code paths (base URL normalization, payload building, SSE parsing,
validation, error handling, executor tool-call parsing) without a live
``llama-server`` binary or ``.gguf`` weights.  The server runs in-process on an
ephemeral port, is always available, and drives the real ``requests`` client.

Routes (matching the llama.cpp OpenAI-compatible API served under ``/v1``):

  GET  /v1/models           -> JSON model list
  POST /v1/chat/completions -> JSON chat completion, or SSE stream (stream=true)
  POST /v1/embeddings       -> JSON embeddings payload

The server is fully configurable per route via a :class:`ServerConfig` object,
so tests can drive content, usage, streaming chunks, embedding vectors, index
schemes, and error injection.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from laew.llm.base import LLMError


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threading HTTP server for the llama.cpp test harness.

    Each connection is handled in its own daemon thread, so a client that keeps
    a connection alive (HTTP/1.1 keep-alive) blocks only that thread — a
    second request to the same server does not hang.  ``daemon_threads`` and
    ``allow_reuse_address`` keep shutdown prompt and socket reuse clean.
    """

    daemon_threads = True
    allow_reuse_address = True


class ServerConfig:
    """Per-route configuration for the llama.cpp test server.

    Attributes:
        models: Advertised model list for ``GET /v1/models``.  Each entry is a
            dict with ``id`` and optional ``created`` / ``owned_by``.
        chat_content: Plain-text assistant reply for non-streaming chat.
        tool_call_content: When set, chat replies with a fenced ``tool_call``
            block instead of ``chat_content`` (LAEW text-based tool protocol).
        chat_usage: Optional ``usage`` block; when omitted the token counts are
            left ``None`` (exercising the no-usage branch).
        chat_error / chat_error_status: Optional error injection for chat.
        chat_stream_chunks: List of SSE frame dicts; each is a full delta frame
            (with ``finish_reason`` on the last).  When None, ``chat_content``
            is streamed as a single chunk.
        embedding_dim: Real vector length reported by the (fake) model.
        embedding_index_mode: One of ``sequential`` (default), ``out-of-order``,
            ``duplicate`` (raises), or ``missing`` (raises).
        embedding_vectors: Per-input embedding vectors (length ``embedding_dim``
            unless ``index_mode == "wrong-dimension"``).
        embedding_error / embedding_error_status: Optional error injection.
        pooling: Echoed by the request; the llama.cpp client sends no ``pooling``
            param (pooling is a server-side model capability).
        call_count: Mutable counter of route hits (``models`` / ``chat`` /
            ``embeddings``).
    """

    def __init__(self):
        self.models = [
            {"id": "gpt-oss-20b-q4", "created": 0, "owned_by": "server"},
            {"id": "nomic-embed-text", "created": 0, "owned_by": "server"},
        ]
        self.chat_content = "Hello! I am a llama.cpp chat assistant."
        self.tool_call_content = None
        self.chat_usage = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
        self.chat_error = None
        self.chat_error_status = None

        self.chat_stream_chunks = [
            {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "!"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": " llama.cpp"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": " assistant."}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
        ]

        self.embedding_dim = 768
        self.embedding_index_mode = "sequential"
        self.embedding_vectors = [
            [0.0] * self.embedding_dim,
            [0.5] * self.embedding_dim,
            [0.9] * self.embedding_dim,
        ]
        self.embedding_error = None
        self.embedding_error_status = None
        self.pooling = "default"
        self.call_count = {"models": 0, "chat": 0, "embeddings": 0}
        # Scripted sequence of chat responses (indexed in call order), used to
        # drive multi-step executor runs (tool_call block, then final answer).
        self.chat_sequence = None
        self._chat_call_index = 0
        # Captured request bodies (for asserting payload shape).
        self.last_chat_request = None
        self.last_embedding_request = None

    def build_models_payload(self):
        return {
            "object": "list",
            "data": [
                {
                    "id": m["id"],
                    "object": "model",
                    "created": m.get("created", 0),
                    "owned_by": m.get("owned_by", "server"),
                }
                for m in self.models
            ],
        }

    def _next_chat_content(self):
        """Return the next scripted chat content, cycling through the sequence."""
        if self.chat_sequence is not None:
            content = self.chat_sequence[self._chat_call_index % len(self.chat_sequence)]
            self._chat_call_index += 1
            return content
        content = (
            self.tool_call_content
            if self.tool_call_content is not None
            else self.chat_content
        )
        return content

    def build_chat_response(self):
        content = self._next_chat_content()
        return {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": self.models[0]["id"] if self.models else "gpt-oss-20b-q4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": self.chat_usage,
        }

    def build_embeddings_payload(self, request):
        """Build the embeddings payload for the current config.

        The request body is accepted (the llama.cpp client sends it) but its
        ``pooling`` param is not required — pooling is a server-side model
        capability.  The payload returns **exactly one entry per input** in the
        request, keyed by ``0..N-1`` (or the scripted index scheme).  The
        index scheme is driven by ``embedding_index_mode``.
        """
        inputs = request.get("input")
        if isinstance(inputs, str):
            inputs = [inputs]
        n = len(inputs)
        if n == 0:
            # No inputs: an empty data list (the client validates this).
            return {"object": "list", "data": []}

        if self.embedding_index_mode == "wrong-dimension":
            vectors = [list(v) + [0.0] for v in self.embedding_vectors]
        else:
            vectors = self.embedding_vectors

        if self.embedding_index_mode == "sequential":
            indices = list(range(n))
        elif self.embedding_index_mode == "out-of-order":
            indices = [0, 2, 1]  # entries returned out of input order
            # Each entry's index and embedding refer to the same input
            # (embedding_vectors[idx]); the client keys by index and reorders
            # to input order.
            data = [
                {"index": idx, "embedding": vectors[idx]} for idx in indices
            ]
            return {"object": "list", "data": data}
        elif self.embedding_index_mode == "duplicate":
            indices = [0, 0]
        elif self.embedding_index_mode == "missing":
            # Only indexes 0 and 1 for three inputs -> index 2 is missing.
            indices = [0, 1]
        else:
            indices = list(range(n))

        return {
            "object": "list",
            "data": [
                {"index": i, "embedding": v, "object": "embedding"}
                for i, v in zip(indices, vectors)
            ],
        }


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Close idle keep-alive connections after a grace period so a connection
    # that never sends another request doesn't pin a handler thread forever.
    timeout = 10

    def log_message(self, *args):  # silence request logging
        pass

    def _send(self, code, body_bytes, headers=None):
        self.send_response(code)
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _error(self, code, message):
        self._send(
            code,
            json.dumps(
                {"error": {"message": message, "type": "httpError", "code": str(code)}}
            ).encode(),
        )

    def do_GET(self):
        if self.path == "/v1/models":
            self.server.config.call_count["models"] += 1
            self._send(
                200,
                json.dumps(self.server.config.build_models_payload()).encode(),
            )
            return
        self._error(404, "not found")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b""
        try:
            request = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            request = {}

        if self.path == "/v1/chat/completions":
            self._handle_chat(request)
        elif self.path == "/v1/embeddings":
            self._handle_embeddings(request)
        else:
            self._error(404, "not found")

    def _handle_chat(self, request):
        config = self.server.config
        config.last_chat_request = request
        if config.chat_error:
            status = config.chat_error_status or 500
            self._error(status, config.chat_error)
            return
        if request.get("stream"):
            self._send_stream()
            return
        self._send(200, json.dumps(config.build_chat_response()).encode())

    def _send_stream(self):
        config = self.server.config
        chunks = config.chat_stream_chunks or []
        lines = [f"data: {json.dumps(chunk)}" for chunk in chunks]
        # Real llama.cpp streams a final usage frame before [DONE]; emit one so
        # the client can account tokens from the stream without a separate call.
        if config.chat_usage:
            lines.append(f"data: {json.dumps({'usage': config.chat_usage})}")
        lines.append("data: [DONE]")
        body = "\n".join(lines) + "\n"
        self._send(200, body.encode("utf-8"), headers={"Content-Type": "text/event-stream"})

    def _handle_embeddings(self, request):
        config = self.server.config
        config.call_count["embeddings"] += 1
        config.last_embedding_request = request
        if config.embedding_error:
            status = config.embedding_error_status or 500
            self._error(status, config.embedding_error)
            return
        self._send(200, json.dumps(config.build_embeddings_payload(request)).encode())


class LlamaCppTestServer:
    """A configurable, in-process llama.cpp OpenAI-compatible HTTP server.

    Starts on an ephemeral port in a daemon thread; the returned base URL
    already ends in ``/v1``.  Always available (no external dependency), so
    integration tests run rather than skip.
    """

    def __init__(self, config=None):
        self.config = config or ServerConfig()
        self._httpd = None
        self._thread = None
        self._base_url = None

    def start(self):
        self._httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.config = self.config
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True
        )
        self._thread.start()
        _, port = self._httpd.server_address
        self._base_url = f"http://127.0.0.1:{port}/v1"
        # Exposed as ``base_url`` so callers (e.g. integration tests) can read
        # the resolved URL from the server instance directly.
        self.base_url = self._base_url
        return self._base_url

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)
