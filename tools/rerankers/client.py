"""Standalone normalization client; no production LAEW imports or dependencies."""
import argparse
import json
import math
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

MODELS = {
    "gte": {"model_id": "Alibaba-NLP/gte-multilingual-reranker-base",
            "revision": "8215cf04918ba6f7b6a62bb44238ce2953d8831c", "port": 8083,
            "backend": "tei-cpu-1.9.4"},
    "bge": {"model_id": "BAAI/bge-reranker-v2-m3",
            "revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", "port": 8084,
            "backend": "tei-cpu-1.9.4"},
    "mxbai": {"model_id": "mixedbread-ai/mxbai-rerank-base-v2",
              "revision": "3ea9d4dffa7d12a4f366be8e275c349de9fc9865", "port": 8085,
              "backend": "mxbai-rerank-0.1.6/torch-2.6.0+cpu"},
}
MAX_DOCUMENTS = 16
MAX_TEXT_CHARS = 16000
MAX_QUERY_CHARS = 2000
MAX_BODY_BYTES = 524288


class RerankError(RuntimeError):
    """An explicit transport, validation, availability or backend error."""


def validate_request(value):
    """Strict, bounded logical request. Duplicate text is allowed; IDs are unique."""
    if not isinstance(value, dict) or set(value) - {"query", "documents", "truncate"}:
        raise ValueError("Expected query, documents and optional truncate")
    query, documents = value.get("query"), value.get("documents")
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
        raise ValueError("Query must contain 1..2000 characters")
    if not isinstance(documents, list) or not 1 <= len(documents) <= MAX_DOCUMENTS:
        raise ValueError("Expected 1..16 documents")
    ids = set()
    for document in documents:
        if not isinstance(document, dict) or set(document) != {"id", "text"}:
            raise ValueError("Each document requires only id and text")
        identifier, text = document["id"], document["text"]
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 128 or identifier in ids:
            raise ValueError("Document IDs must be unique, nonempty strings of at most 128 characters")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS:
            raise ValueError("Document text must contain 1..16000 characters")
        ids.add(identifier)
    if type(value.get("truncate", False)) is not bool:
        raise ValueError("truncate must be boolean")
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("Request exceeds byte limit")
    return value


def normalize_results(documents, rows):
    """Require a bijection and finite scores; ties retain the input order."""
    if not isinstance(rows, list) or len(rows) != len(documents):
        raise RerankError("Backend returned an incomplete ranking")
    results, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise RerankError("Malformed ranking row")
        index, score = row.get("index"), row.get("score")
        if type(index) is not int or not 0 <= index < len(documents) or index in seen:
            raise RerankError("Invalid or repeated document index")
        if type(score) not in (float, int) or not math.isfinite(score):
            raise RerankError("Backend returned a non-finite score")
        seen.add(index)
        results.append({"id": documents[index]["id"], "index": index, "score": float(score)})
    return sorted(results, key=lambda row: (-row["score"], row["index"]))


class RerankerClient:
    def __init__(self, model, base_url=None, timeout=120):
        if model not in MODELS or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Unknown model or invalid timeout")
        self.model = model
        self.base_url = (base_url or f"http://127.0.0.1:{MODELS[model]['port']}").rstrip("/")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _request(self, path, body=None):
        request = urllib.request.Request(self.base_url + path,
                                        data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                        headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read(MAX_BODY_BYTES * 16 + 1)
                if len(payload) > MAX_BODY_BYTES * 16:
                    raise RerankError("Backend response exceeds limit")
                result = json.loads(payload) if payload else None
                return result, {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as error:
            # Do not include a backend body: it may contain private request text.
            raise RerankError(f"Backend HTTP {error.code}") from None
        except (TimeoutError, socket.timeout):
            raise RerankError("Request timed out; backend work may still be running") from None
        except urllib.error.URLError as error:
            category = "timeout" if isinstance(error.reason, TimeoutError) else "unavailable"
            raise RerankError(f"Backend {category}") from None
        except (ValueError, OSError):
            raise RerankError("Invalid response or transport failure") from None

    def ready(self):
        """Logical GET /readyz; TEI maps to its native GET /health."""
        self._request("/readyz" if self.model == "mxbai" else "/health")
        return True

    def info(self):
        """Logical GET /v1/info; verify actual model identity and revision."""
        native, _ = self._request("/v1/info" if self.model == "mxbai" else "/info")
        expected = MODELS[self.model]
        if not isinstance(native, dict) or native.get("model_id") != expected["model_id"]:
            raise RerankError("Unexpected backend model")
        revision = native.get("revision", native.get("model_sha"))
        if revision != expected["revision"]:
            raise RerankError("Unexpected backend revision")
        return {**expected, "native": native, "effective_token_limit": 1024,
                "max_documents": MAX_DOCUMENTS, "device": "cpu"}

    def rerank(self, value):
        value = validate_request(value)
        started = time.perf_counter()
        info = self.info()
        if self.model == "mxbai":
            result, _ = self._request("/v1/rerank", value)
            if (not isinstance(result, dict) or not {"results", "inference_ms", "truncated_indices"} <= result.keys()
                    or not isinstance(result["truncated_indices"], list)
                    or any(type(i) is not int or not 0 <= i < len(value["documents"]) for i in result["truncated_indices"])):
                raise RerankError("Malformed backend response")
            rows = result["results"]
            inference_ms = result["inference_ms"]
            truncation = {"requested": value.get("truncate", False),
                          "indices": result["truncated_indices"], "status": "exact"}
        else:
            rows, headers = self._request("/rerank", {
                "query": value["query"], "texts": [doc["text"] for doc in value["documents"]],
                "truncate": value.get("truncate", False), "raw_scores": True, "return_text": False,
            })
            try:
                inference_ms = float(headers["x-inference-time"]) if "x-inference-time" in headers else None
            except (TypeError, ValueError):
                raise RerankError("Malformed backend latency") from None
            # TEI does not expose per-pair truncation flags. Never report unknown as false.
            truncation = {"requested": value.get("truncate", False), "indices": None,
                          "status": "unknown" if value.get("truncate", False) else "none"}
        if inference_ms is not None and (type(inference_ms) not in (int, float) or not math.isfinite(inference_ms) or inference_ms < 0):
            raise RerankError("Malformed backend latency")
        return {"model_id": info["model_id"], "revision": info["revision"],
                "backend": info["backend"], "candidate_count": len(value["documents"]),
                "results": normalize_results(value["documents"], rows),
                "inference_ms": inference_ms, "request_ms": (time.perf_counter() - started) * 1000,
                "truncation": truncation}


def docker_stats(model):
    try:
        result = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}",
                                 f"laew-reranker-{model}-1"], capture_output=True, text=True, timeout=10)
        return json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def docker_counters(model):
    """Cgroup CPU time/current/peak memory, supporting Docker Desktop v1 and v2."""
    container = f"laew-reranker-{model}-1"
    variants = [
        ["/sys/fs/cgroup/cpuacct/cpuacct.usage", "/sys/fs/cgroup/memory/memory.usage_in_bytes", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"],
        ["/sys/fs/cgroup/cpu.stat", "/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.peak"],
    ]
    for index, paths in enumerate(variants):
        try:
            result = subprocess.run(["docker", "exec", container, "cat", *paths], capture_output=True, text=True, timeout=10)
            if result.returncode:
                continue
            lines = result.stdout.strip().splitlines()
            cpu = int(lines[0]) // 1000 if index == 0 else int(next(line.split()[1] for line in lines[:-2] if line.startswith("usage_usec ")))
            return {"usage_usec": cpu, "memory_current": int(lines[-2]), "memory_peak": int(lines[-1])}
        except (OSError, ValueError, IndexError, StopIteration, subprocess.TimeoutExpired):
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=MODELS)
    parser.add_argument("operation", choices=("ready", "info", "rerank"))
    parser.add_argument("--input", type=Path, help="Logical request JSON")
    parser.add_argument("--output", type=Path, help="Append JSONL, without document contents")
    parser.add_argument("--base-url")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()
    counters_before = docker_counters(args.model) if args.stats else None
    started = time.perf_counter()
    try:
        client = RerankerClient(args.model, args.base_url, args.timeout)
        if args.operation == "rerank":
            if not args.input:
                parser.error("rerank requires --input")
            result = client.rerank(json.loads(args.input.read_text(encoding="utf-8")))
        else:
            result = {"ready": client.ready()} if args.operation == "ready" else client.info()
        code = 0
    except (RerankError, ValueError, OSError) as error:
        result = {"model_id": MODELS[args.model]["model_id"], "revision": MODELS[args.model]["revision"],
                  "error": str(error) if isinstance(error, RerankError) else type(error).__name__,
                  "request_ms": (time.perf_counter() - started) * 1000}
        code = 1
    if args.stats:
        counters_after = docker_counters(args.model)
        result["cgroup_after"] = counters_after
        if counters_before and counters_after:
            elapsed_seconds = time.perf_counter() - started
            result["cpu_seconds"] = (counters_after["usage_usec"] - counters_before["usage_usec"]) / 1e6
            result["cpu_percent_request_window"] = result["cpu_seconds"] / elapsed_seconds * 100
        result["docker_stats_after_request"] = docker_stats(args.model)
    line = json.dumps(result, ensure_ascii=False, allow_nan=False)
    if args.output:
        with args.output.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
    print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
