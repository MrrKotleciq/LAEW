"""CPU-only HTTP service using the official Mixedbread v2 inference implementation."""
import concurrent.futures
import importlib.metadata
import json
import logging
import math
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from client import MAX_BODY_BYTES, MODELS, normalize_results, validate_request

LOG = logging.getLogger("reranker")


class Runtime:
    def __init__(self):
        self.model = None
        self.failed = False
        self.gate = threading.Lock()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.max_tokens = int(os.environ.get("MAX_INPUT_TOKENS", "1024"))
        self.request_timeout = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "120"))
        if not 64 <= self.max_tokens <= 1024 or not math.isfinite(self.request_timeout) or self.request_timeout <= 0:
            raise ValueError("Invalid resource limits")
        self.model_id = os.environ.get("MODEL_ID", MODELS["mxbai"]["model_id"])
        self.revision = os.environ.get("MODEL_REVISION", MODELS["mxbai"]["revision"])

    def load(self):
        try:
            import torch
            from huggingface_hub import snapshot_download
            from mxbai_rerank import MxbaiRerankV2

            torch.set_num_threads(2)
            torch.set_num_interop_threads(1)
            path = snapshot_download(self.model_id, revision=self.revision,
                                     allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja", "LICENSE"])
            self.model = MxbaiRerankV2(path, device="cpu", torch_dtype=torch.float32,
                                      max_length=self.max_tokens, trust_remote_code=False,
                                      local_files_only=True, attn_implementation="sdpa",
                                      tokenizer_kwargs={"local_files_only": True, "trust_remote_code": False})
            LOG.info("Model ready: %s revision=%s device=cpu", self.model_id, self.revision)
        except Exception as error:
            # Do not log request bodies, tokens, cache URLs or exception messages.
            self.failed = True
            LOG.error("Model initialization failed: %s", type(error).__name__)

    def info(self):
        return {"model_id": self.model_id, "revision": self.revision,
                "backend": MODELS["mxbai"]["backend"], "device": "cpu", "dtype": "float32",
                "max_input_tokens": self.max_tokens, "batch_size": 1, "threads": 2,
                "request_timeout_seconds": self.request_timeout,
                "ready": self.model is not None, "startup_failed": self.failed,
                "dependencies": {name: importlib.metadata.version(name) for name in
                                 ("mxbai-rerank", "torch", "transformers", "huggingface-hub")}}

    def truncated_indices(self, value):
        model = self.model
        tokenizer = model.tokenizer
        query = tokenizer(model.query_prompt.format(query=value["query"]), add_special_tokens=False)["input_ids"]
        indices = []
        for index, doc in enumerate(value["documents"]):
            tokens = tokenizer(model.doc_prompt.format(document=doc["text"]), add_special_tokens=False)["input_ids"]
            if len(query) > model.max_length * 3 // 4 or len(query) + len(model.sep_inputs) + len(tokens) > model.max_length:
                indices.append(index)
        return indices

    def score(self, value):
        try:
            truncated = self.truncated_indices(value)
            if truncated and not value.get("truncate", False):
                raise ValueError("Input exceeds token budget; explicitly set truncate=true")
            started = time.perf_counter()
            # Batch one preserves mapping and bounds the full-vocabulary decoder logits.
            rows = [{"index": i, "score": float(self.model.predict([value["query"]], [doc["text"]], normalize=False)[0])}
                    for i, doc in enumerate(value["documents"])]
            return {"results": normalize_results(value["documents"], rows),
                    "inference_ms": (time.perf_counter() - started) * 1000,
                    "truncated_indices": truncated}
        finally:
            self.gate.release()


def handler_for(runtime):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No document contents, query strings or private headers in access logs.

        def reply(self, status, body):
            payload = json.dumps(body, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.path == "/readyz":
                self.reply(200 if runtime.model is not None else 503,
                           {"ready": runtime.model is not None, "startup_failed": runtime.failed})
            elif self.path == "/v1/info":
                self.reply(200, runtime.info())
            else:
                self.reply(404, {"error": "Unknown endpoint"})

        def do_POST(self):
            if self.path != "/v1/rerank":
                return self.reply(404, {"error": "Unknown endpoint"})
            if runtime.model is None:
                return self.reply(503, {"error": "Model unavailable", "startup_failed": runtime.failed})
            try:
                if self.headers.get("Transfer-Encoding") or self.headers.get_content_type() != "application/json":
                    return self.reply(400, {"error": "Expected bounded JSON request"})
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY_BYTES:
                    return self.reply(413, {"error": "Invalid body length"})
                self.connection.settimeout(10)
                value = validate_request(json.loads(self.rfile.read(length)))
            except (ValueError, OSError, UnicodeError):
                return self.reply(400, {"error": "Malformed or out-of-bounds request"})
            if not runtime.gate.acquire(blocking=False):
                return self.reply(429, {"error": "Model busy; retry after current inference completes"})
            future = runtime.executor.submit(runtime.score, value)
            try:
                self.reply(200, future.result(timeout=runtime.request_timeout))
            except concurrent.futures.TimeoutError:
                self.reply(504, {"error": "Inference timeout; worker remains busy until completion"})
            except ValueError:
                self.reply(422, {"error": "Input exceeds token budget; explicitly set truncate=true"})
            except Exception as error:
                LOG.error("Inference failed: %s", type(error).__name__)
                self.reply(500, {"error": "Inference failed"})

    return Handler


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    runtime = Runtime()
    threading.Thread(target=runtime.load, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 8080), handler_for(runtime))

    def stop(signum, frame):
        # shutdown() must run outside serve_forever's thread. PID 1 otherwise
        # ignores default SIGTERM, making Docker force-kill a healthy service.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        runtime.executor.shutdown(wait=True, cancel_futures=True)
        LOG.info("Service stopped")


if __name__ == "__main__":
    main()
