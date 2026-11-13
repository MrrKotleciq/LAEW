"""Isolated lexical retrieval benchmark, Task 1: no fusion or runtime integration."""
import argparse
from collections import defaultdict
from copy import deepcopy
import csv
import ctypes
import gzip
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
import uuid
from unittest.mock import patch

DATASETS = ("baseline_v1", "hard_cases_v1", "reranker_holdout_v1", "evidence_supplement_v1")
KS = (5, 10, 20, 50)


def read(path):
    opener = gzip.open if Path(path).suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig") as stream:
        return json.load(stream)


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def record(chunk):
    return {"id": chunk.chunk_id, "text": chunk.text, "source": chunk.source,
            "path": chunk.file_path, "metadata": chunk.metadata}


def collect(pipeline, dataset, known_sources):
    from laew.eval.reranker_benchmark import atom_present
    from laew.rag.knowledge_base import KnowledgeScope
    kb = pipeline.knowledge_base
    chunks, counts = [], {}
    for scope, store in (("global", kb.global_store), ("project", kb.project_store)):
        actual = store.sync_records(scope)
        counts[scope] = len(actual)
        data = store._collection.get(include=["embeddings"])
        vectors = dict(zip(data["ids"], data["embeddings"]))
        chunks.extend(record(c) | {"embedding": [float(x) for x in vectors[c.chunk_id]]} for c in actual)
    queries = []
    for q in dataset["queries"]:
        started = time.perf_counter()
        vector = pipeline.embedding_service.embed(q["text"])
        embedding_ms = (time.perf_counter() - started) * 1000
        scopes = ("project", "global") if q["allowed_scope"] == "hybrid" else (q["allowed_scope"],)
        searches = {}
        for scope in scopes:
            searches[scope] = {}
            for k in KS:
                pairs = pipeline._retrieve_candidates(vector, KnowledgeScope(scope), min(k, counts[scope]))
                if any(c.source != scope for c, _ in pairs):
                    raise RuntimeError("Scope escaped fixture collection")
                searches[scope][str(k)] = [{"id": c.chunk_id, "score": score} for c, score in pairs]
        all_chunks = [c for scope, store in (("global", kb.global_store), ("project", kb.project_store)) for c in store.sync_records(scope)]
        queries.append({"query": q, "embedding": vector, "embedding_ms": embedding_ms, "dense": searches,
                        "index_atom_available": [any(atom_present(a, c) for c in all_chunks) for a in q["evidence"]]})
    return {"chunks": chunks, "queries": queries, "document_languages": dataset.get("document_languages", {}),
            "sources": sorted(known_sources)}


def stress_chunks(embedding):
    """Exact previous generator; no change to old implementation or artifacts."""
    from laew.rag.knowledge_base import KnowledgeBase
    from laew.rag.vector_store import DocumentChunk
    root = Path("tests/rag/evidence_supplement_v1")
    kb = KnowledgeBase(str(root / "project"), str(root / "global"), embedding, vector_store_config={"enabled": False})
    chunks = kb._load_file(root / "global/atlas.md", "global", root / "global", embed=False)
    topics = ["storage queue", "clock synchronization", "firmware recovery", "build artifacts", "transaction snapshots",
              "connector inspection", "data acquisition", "network telemetry", "sensor calibration", "release validation",
              "checksum verification", "event triggers", "database checkpoints", "sample buffering", "cable shielding", "audit records"]
    for i in range(1024):
        topic, other = topics[i % len(topics)], topics[(i // len(topics)) % len(topics)]
        text = (f"Synthetic distractor engineering record {i}. Subsystem {topic}, review area {other}. "
                f"Device group {i // 16} schedules inspection after {i % 29 + 1} operating cycles. "
                f"This fixture discusses maintenance logging, reference measurements and test preparation. "
                f"Record {i} supplies no Atlas firmware prerequisites or acceptance limits. "
                f"Its numeric tracking value is {i * 17 + 3} and its channel group is {i % 64}.")
        chunks.append(DocumentChunk(f"stress-{i}", text, source="global", file_path=f"stress/{i}.md"))
    return chunks


def prepare(previous_stress):
    from laew.eval import rag_baseline as baseline
    from laew.manifest import load_manifest
    from laew.runtime import build_embedding_service
    manifest = load_manifest("manifests/SYSTEM_MANIFEST.yaml")
    embedding = build_embedding_service(manifest)
    conditions = []
    for name in DATASETS:
        root = Path("tests/rag") / name
        if (root / "FREEZE.json").exists():
            for path, expected in read(root / "FREEZE.json")["sha256"].items():
                if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
                    raise ValueError("Frozen fixture changed")
        for chunker in ("legacy", "structure-v2"):
            print(f"Preparing {name}/{chunker}", flush=True)
            with patch.object(baseline, "evaluate", collect):
                result = baseline.run(Path("manifests/SYSTEM_MANIFEST.yaml"), root, chunker)
            result["dataset_directory"] = name
            conditions.append(result)
    chunks = stress_chunks(embedding)
    old = read(previous_stress)
    corpus_hash = digest([c.to_dict() for c in chunks])
    if corpus_hash != old["corpus_hash"] or len(chunks) != old["total_chunks"]:
        raise ValueError("Stress corpus does not reproduce previous corpus hash")
    started = time.perf_counter()
    for offset in range(0, len(chunks), 16):
        batch = chunks[offset:offset + 16]
        vectors = embedding.embed_batch([c.text for c in batch])
        for c, vector in zip(batch, vectors):
            c.embedding = vector
        if offset % 128 == 0:
            print(f"Stress embedded {offset + len(batch)}/{len(chunks)}", flush=True)
    stress = {"dataset_directory": "stress_1036", "chunking": {"strategy": "legacy"},
              "chunks": [record(c) | {"embedding": c.embedding} for c in chunks],
              "embedding_seconds": time.perf_counter() - started, "previous_corpus_hash": corpus_hash,
              "document_languages": {"@knowledge/atlas.md": "en"}, "queries": []}
    from laew.eval.reranker_benchmark import atom_present
    for q in read(Path("tests/rag/evidence_supplement_v1/dataset.json"))["queries"]:
        if q["topic_id"] == "atlas":
            started = time.perf_counter()
            vector = embedding.embed(q["text"])
            stress["queries"].append({"query": q, "embedding": vector, "embedding_ms": (time.perf_counter() - started) * 1000,
                                      "index_atom_available": [any(atom_present(a, c) for c in chunks) for a in q["evidence"]]})
    conditions.append(stress)
    return {"protocol": "lexical-task1-v1", "conditions": conditions, "content_hash": digest(conditions),
            "embedding_model": embedding.model, "dimensions": embedding.dimensions}


def hydrate(r):
    from laew.rag.vector_store import DocumentChunk
    return DocumentChunk(r["id"], r["text"], embedding=r.get("embedding"), source=r["source"], file_path=r["path"], metadata=r["metadata"])


def stats(values):
    from laew.eval.reranker_benchmark import percentile
    return {"mean": statistics.mean(values), "median": statistics.median(values), "p95": percentile(values, .95), "max": max(values)}


def rss():
    """Windows current and lifetime peak working set; includes native allocations."""
    if os.name != "nt":
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"working_set_bytes": counters.WorkingSetSize, "peak_working_set_bytes": counters.PeakWorkingSetSize}


class DenseIndex:
    """Existing ChromaVectorStore, disposable PersistentClient and cached vectors."""
    def __init__(self, path, binding):
        import chromadb
        from laew.rag.vector_store import ChromaVectorStore
        self.path = Path(path)
        self.binding = binding
        self.client = chromadb.PersistentClient(path=str(path))
        with patch("laew.rag.vector_store._build_chroma_client", return_value=self.client):
            self.store = ChromaVectorStore(collection_name="lexical_dense_fixture", source=binding.scope, embedding_model_id="cached-fixture")
        self.count = self.store.count()

    def rebuild(self, records):
        self.store.add_chunks([hydrate(r) for r in records])
        self.count = self.store.count()

    def search(self, vector, k):
        from laew.rag.lexical_experiment import Hit
        pairs = self.store.search(vector, top_k=min(k, self.count))
        return [Hit(record(c), score) for c, score in pairs]

    def close(self):
        self.client.close()


def index_class(backend):
    from laew.rag.lexical_experiment import FTS5Index, BM25SIndex
    return {"dense": DenseIndex, "fts5": FTS5Index, "bm25s": BM25SIndex}[backend]


def measure_resource(payload, backend, path):
    """Fresh-process observations, including publication and mutations."""
    from laew.rag.lexical_experiment import Binding
    before = rss()
    started = time.perf_counter()
    cls = index_class(backend)
    index = cls(path, Binding("resource", "global"))
    open_seconds = time.perf_counter() - started
    opened = rss()
    records = payload["chunks"]
    started = time.perf_counter()
    index.rebuild(records)
    build_seconds = time.perf_counter() - started
    after = rss()
    queries = payload["queries"]
    for item in queries:
        index.search(item["embedding"] if backend == "dense" else item["query"]["text"], 20)
    warmed = rss()
    mutation = []
    # Fixed generic probes, independent of relevance labels and query outcomes.
    if backend != "dense":
        current = deepcopy(records)
        added = {"id": "mutation-added", "text": "zzlexicaladdedtoken new procedure", "source": "global", "path": "mutation.md", "metadata": {"revision": 1}}
        changed = {k: records[0][k] for k in ("id", "text", "source", "path", "metadata")}
        changed = deepcopy(changed)
        changed["text"] = "zzlexicalupdatedtoken replacement procedure"
        changed["metadata"]["revision"] = 2
        for operation, upserts, deletes in (("add", [added], []), ("update", [changed], []), ("delete", [], [added["id"]])):
            started = time.perf_counter()
            index.mutate(upserts=upserts, deletes=deletes)
            elapsed = time.perf_counter() - started
            expected = {r["id"]: r for r in current if r["id"] not in deletes}
            expected.update({r["id"]: r for r in upserts})
            current = list(expected.values())
            if operation == "add":
                valid = any(h.record["id"] == added["id"] for h in index.search("zzlexicaladdedtoken", 20))
            elif operation == "update":
                valid = any(h.record["id"] == changed["id"] for h in index.search("zzlexicalupdatedtoken", 20))
            else:
                valid = not index.search("zzlexicaladdedtoken", 20)
            mutation.append({"operation": operation, "seconds": elapsed, "verified": valid,
                             "implementation": "transactional incremental" if backend == "fts5" else "full snapshot rebuild"})
        fresh = cls(Path(path).with_name(Path(path).name + "-clean"), index.binding)
        try:
            started = time.perf_counter()
            fresh.rebuild(current)
            rebuild_seconds = time.perf_counter() - started
            checks = ["zzlexicalupdatedtoken", "firmware acceptance", "checkpoint clock"]
            clean_equal = all([(h.record["id"], h.score) for h in index.search(q, 50)] ==
                              [(h.record["id"], h.score) for h in fresh.search(q, 50)] for q in checks)
        finally:
            fresh.close()
    else:
        rebuild_seconds, clean_equal = None, None
    index.close()
    started = time.perf_counter()
    index = cls(path, Binding("resource", "global"))
    load_seconds = time.perf_counter() - started
    loaded = rss()
    if backend != "dense":
        reload_valid = any(h.record["id"] == changed["id"] for h in index.search("zzlexicalupdatedtoken", 20))
    else:
        reload_valid = bool(index.search(queries[0]["embedding"], 20))
    index.close()
    path = Path(path)
    total_bytes = sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else path.stat().st_size
    active_bytes = total_bytes
    if backend == "bm25s":
        generation = read(path / "CURRENT.json")["generation"]
        active_bytes = sum(p.stat().st_size for p in (path / generation).rglob("*") if p.is_file()) + sum(p.stat().st_size for p in path.iterdir() if p.is_file())
    # Separate traced rebuild excludes imports and does not contaminate wall times.
    trace_path = path.with_name(path.name + "-trace")
    trace = cls(trace_path, Binding("trace", "global"))
    try:
        tracemalloc.start()
        trace.rebuild(records)
        _, python_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    finally:
        trace.close()
    return {"backend": backend, "chunks": len(records), "backend_import_and_open_seconds": open_seconds, "build_publish_seconds": build_seconds,
            "rss_before_backend_import": before, "rss_after_open": opened, "rss_after_build": after, "rss_warm": warmed, "rss_reloaded": loaded,
            "python_traced_build_peak_bytes": python_peak, "mutations": mutation, "clean_rebuild_seconds": rebuild_seconds,
            "post_mutation_equals_clean": clean_equal, "reload_seconds": load_seconds, "reload_verified": reload_valid,
            "active_index_bytes_after_mutations": active_bytes, "retained_index_bytes_after_mutations": total_bytes}


def resource_probes(pool):
    """Sequential subprocesses: backend imports/allocations cannot leak into peers."""
    results = []
    with tempfile.TemporaryDirectory(prefix="laew-lexical-resource-") as scratch:
        root = Path(scratch)
        for condition in pool["conditions"]:
            if condition["dataset_directory"] not in ("reranker_holdout_v1", "stress_1036") or condition["chunking"]["strategy"] != "legacy":
                continue
            payload = {"chunks": [r for r in condition["chunks"] if r["source"] == "global"],
                       "queries": [r for r in condition["queries"] if r["query"]["allowed_scope"] == "global"]}
            input_path = root / "input.json"
            write(input_path, payload)
            for backend in ("fts5", "bm25s", "dense"):
                output = root / f"{condition['dataset_directory']}-{backend}.json"
                subprocess.run([sys.executable, "-m", "laew.eval.lexical_benchmark", "resource", "--input", str(input_path), "--backend", backend,
                                "--index-path", str(root / f"index-{condition['dataset_directory']}-{backend}"), "--output", str(output)], check=True)
                results.append({"dataset": condition["dataset_directory"]} | read(output))
    return results


def benchmark(pool, repeats=20):
    from laew.eval.reranker_benchmark import atom_present, rank_metrics
    from laew.rag.lexical_experiment import Binding
    if pool["content_hash"] != digest(pool["conditions"]):
        raise ValueError("Cached corpus changed")
    rows, s14, exact_diagnostics = [], [], []
    with tempfile.TemporaryDirectory(prefix="laew-lexical-quality-") as scratch:
        root = Path(scratch)
        for ci, condition in enumerate(pool["conditions"]):
            indexes = {}
            try:
                for scope in ("global", "project"):
                    # Preserve captured/generator insertion order for HNSW.
                    # Lexical ties are independently resolved by stable IDs.
                    records = [r for r in condition["chunks"] if r["source"] == scope]
                    if not records:
                        continue
                    binding = Binding(condition["dataset_directory"] + "/" + condition["chunking"]["strategy"], scope,
                                      "fixture-project" if scope == "project" else None)
                    for backend in ("dense", "fts5", "bm25s"):
                        index = index_class(backend)(root / f"{ci}-{scope}-{backend}", binding)
                        index.rebuild(records)
                        indexes[scope, backend] = index
                for item in condition["queries"]:
                    q = item["query"]
                    scopes = ("project", "global") if q["allowed_scope"] == "hybrid" else (q["allowed_scope"],)
                    for k in KS:
                        for backend in ("dense", "fts5", "bm25s"):
                            hit_scopes, timings = {}, {}
                            for scope in scopes:
                                index = indexes[scope, backend]
                                argument = item["embedding"] if backend == "dense" else q["text"]
                                index.search(argument, k)
                                samples = []
                                for _ in range(repeats):
                                    started = time.perf_counter()
                                    hits = index.search(argument, k)
                                    samples.append((time.perf_counter() - started) * 1000)
                                hit_scopes[scope] = hits
                                timings[scope] = stats(samples)
                            variants = (("dense_raw", hit_scopes), ("dense_eligible", {s: [h for h in hs if h.score >= .3] for s, hs in hit_scopes.items()})) if backend == "dense" else ((backend, hit_scopes),)
                            for name, scoped in variants:
                                hits = [h for hs in scoped.values() for h in hs]
                                pairs = [(hydrate(h.record), h.score) for h in hits]
                                if any(c.source not in scopes for c, _ in pairs):
                                    raise RuntimeError("Scope isolation failed")
                                relevant = {d for d, grade in q["relevance"].items() if grade > 0}
                                metrics = rank_metrics(q, pairs)
                                rows.append({"dataset": condition["dataset_directory"], "chunker": condition["chunking"]["strategy"],
                                    "query_id": q["id"], "language": q["language"], "topic_id": q.get("topic_id", q["id"]),
                                    "backend": name, "k": k, "no_answer": bool(q["no_answer"]),
                                    "multi_document": len(q["expected_document_ids"]) > 1,
                                    "cross_language": any(condition.get("document_languages", {}).get(d) not in (None, q["language"]) for d in q["expected_document_ids"]),
                                    "metrics": metrics, "index_atom_available": item["index_atom_available"],
                                    "hits": [{"id": c.chunk_id, "source": c.source, "path": c.file_path, "score": score} for c, score in pairs],
                                    "count_per_scope": {s: len(hs) for s, hs in scoped.items()},
                                    "irrelevant_fragments": sum(("@knowledge/" if c.source == "global" else "@project/") + c.file_path.replace(chr(92), "/") not in relevant for c, _ in pairs),
                                    "timing_per_scope_ms": timings, "cached_query_embedding_ms": item.get("embedding_ms")})
                    if q["id"] == "s14":
                        for backend in ("dense", "fts5", "bm25s"):
                            index = indexes["global", backend]
                            hits = index.search(item["embedding"] if backend == "dense" else q["text"], len(condition["chunks"]))
                            s14.append({"dataset": condition["dataset_directory"], "chunker": condition["chunking"]["strategy"], "backend": backend,
                                        "atom_ranks": [next((i for i, h in enumerate(hits, 1) if atom_present(a, hydrate(h.record))), None) for a in q["evidence"]],
                                        "positive_or_dense_matches": len(hits), "index_atom_available": item["index_atom_available"],
                                        "top50": [{"id": h.record["id"], "score": h.score} for h in hits[:50]]})
                print(f"Benchmarked {condition['dataset_directory']}/{condition['chunking']['strategy']}", flush=True)
                if condition["dataset_directory"] == "stress_1036":
                    import numpy as np
                    matrix = np.array([r["embedding"] for r in condition["chunks"]], dtype=np.float64)
                    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
                    for item in condition["queries"]:
                        q = item["query"]
                        vector = np.array(item["embedding"], dtype=np.float64)
                        vector /= np.linalg.norm(vector)
                        scores = matrix @ vector
                        order = np.argsort(-scores, kind="stable")
                        pairs = [(hydrate(condition["chunks"][int(i)]), float(scores[i])) for i in order]
                        exact_diagnostics.append({"query_id": q["id"],
                            "atom_ranks": [next((j for j, (c, _) in enumerate(pairs, 1) if atom_present(a, c)), None) for a in q["evidence"]],
                            "metrics_at_k": {str(k): rank_metrics(q, pairs[:k]) for k in KS},
                            "method": "Exact float64 normalized dot product, diagnostic only; no change to Chroma retrieval"})
            finally:
                for index in indexes.values():
                    index.close()
    return {"protocol": "lexical-task1-v1", "corpus_hash": pool["content_hash"], "repeats": repeats,
            "rows": rows, "summary": summarize(rows), "comparisons": compare(rows), "s14": s14,
            "stress_exact_cosine_diagnostic": exact_diagnostics, "dense_insertion_order": "captured corpus / original stress generator order"}


def architecture():
    """Read-only container identity plus a disposable local API capability probe."""
    import importlib.metadata
    import inspect
    import sqlite3
    import chromadb
    import bm25s
    import requests
    from chromadb import Search, Knn
    from chromadb.api.models.Collection import Collection
    observation = {"client_version": importlib.metadata.version("chromadb"), "sqlite_version": sqlite3.sqlite_version,
                   "bm25s_version": bm25s.__version__, "bm25s_requires": importlib.metadata.requires("bm25s"),
                   "bm25s_native_mutation_methods": [n for n in ("add", "update", "delete", "remove") if hasattr(bm25s.BM25, n)],
                   "collection_search_doc": inspect.getdoc(Collection.search).split("Args:")[0].strip(),
                   "sqlite_fts5_enabled": any("ENABLE_FTS5" in r[0] for r in sqlite3.connect(":memory:").execute("pragma compile_options"))}
    for name, command in (("container_image", ["docker", "inspect", "laew-chromadb-1", "--format", "{{.Image}} {{.Config.Image}}"]),
                          ("binary_version", ["docker", "exec", "laew-chromadb-1", "chroma", "--version"])):
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        observation[name] = {"code": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    try:
        observation["server_version_endpoint"] = requests.get("http://localhost:8000/api/v2/version", timeout=5).json()
        api = requests.get("http://localhost:8000/openapi.json", timeout=5).json()
        observation["server_query_search_paths"] = [p for p in api["paths"] if p.endswith(("/query", "/search"))]
    except requests.RequestException as e:
        observation["server_probe_error"] = str(e)
    with tempfile.TemporaryDirectory(prefix="laew-chroma-capability-") as scratch:
        client = chromadb.PersistentClient(path=scratch)
        try:
            collection = client.create_collection("disposable_native_probe", embedding_function=None)
            collection.add(ids=["probe"], embeddings=[[1., 0.]], documents=["read-only fixture"])
            try:
                observation["local_search_result"] = collection.search(Search().rank(Knn(query=[1., 0.])).limit(1))
            except Exception as error:
                observation["local_search_error"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            client.close()
    return observation


def native_image_probe():
    """Test the exact running image in a disposable container, never production."""
    import chromadb
    from chromadb import Search, Knn
    import requests
    image_id = subprocess.check_output(["docker", "inspect", "laew-chromadb-1", "--format", "{{.Image}}"], text=True).strip()
    name = "laew-lexical-probe-" + uuid.uuid4().hex[:12]
    started = False
    result = {"image_id": image_id, "container": name, "private_or_production_collections_accessed": False,
              "storage": "container-only tmpfs /data, no host volumes", "pull": "never"}
    try:
        subprocess.run(["docker", "run", "-d", "--rm", "--pull=never", "--name", name,
                        "--cpus=1", "--memory=512m", "--tmpfs", "/data:rw,size=128m",
                        "-p", "127.0.0.1:18099:8000", image_id], check=True, capture_output=True, text=True)
        started = True
        deadline = time.monotonic() + 30
        while True:
            try:
                response = requests.get("http://127.0.0.1:18099/api/v2/heartbeat", timeout=1)
                response.raise_for_status()
                break
            except requests.RequestException:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Disposable Chroma probe did not become ready")
                time.sleep(.2)
        client = chromadb.HttpClient(host="127.0.0.1", port=18099)
        collection = client.create_collection("lexical_capability_fixture", embedding_function=None)
        collection.add(ids=["fixture"], documents=["fixture lexical evidence"], embeddings=[[1., 0.]])
        result["query_result"] = collection.query(query_embeddings=[[1., 0.]], n_results=1)["ids"]
        try:
            result["search_result"] = collection.search(Search().rank(Knn(query=[1., 0.])).limit(1))
        except Exception as error:
            result["search_error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if started:
            cleanup = subprocess.run(["docker", "stop", "--time", "3", name], capture_output=True, text=True, timeout=10)
            result["cleanup"] = {"code": cleanup.returncode, "stdout": cleanup.stdout.strip(), "stderr": cleanup.stderr.strip()}
    return result


def summarize(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[tuple(r[k] for k in ("dataset", "chunker", "backend", "k"))].append(r)
    results = []
    for key, group in sorted(grouped.items()):
        answered = [r for r in group if not r["no_answer"]]
        unsupported = [r for r in group if r["no_answer"]]
        def mean(metric, subset):
            return statistics.mean(r["metrics"][metric] for r in subset) if subset else None
        subsets = {"multi_document": [r for r in answered if r["multi_document"]],
                   "cross_language": [r for r in answered if r["cross_language"]]}
        subsets.update({"language_" + language: [r for r in answered if r["language"] == language] for language in sorted({r["language"] for r in group})})
        results.append(dict(zip(("dataset", "chunker", "backend", "k"), key)) | {
            "queries": len(group), "answerable": len(answered), "atom_coverage": mean("evidence_coverage", answered),
            "document_recall": mean("document_recall", answered), "complete_evidence": mean("complete_evidence", answered),
            "subsets": {name: {"n": len(subset), "atom_coverage": mean("evidence_coverage", subset),
                               "document_recall": mean("document_recall", subset), "complete_evidence": mean("complete_evidence", subset)} for name, subset in subsets.items()},
            "unsupported_empty_rate": statistics.mean(not r["hits"] for r in unsupported) if unsupported else None,
            "unsupported_mean_hits": statistics.mean(len(r["hits"]) for r in unsupported) if unsupported else None,
            "mean_returned": statistics.mean(len(r["hits"]) for r in group),
            "irrelevant_fragment_rate": sum(r["irrelevant_fragments"] for r in group) / max(1, sum(len(r["hits"]) for r in group)),
            "scope_search_p50_ms": stats([scope["median"] for r in group for scope in r["timing_per_scope_ms"].values()]),
            "scope_search_p95_ms": stats([scope["p95"] for r in group for scope in r["timing_per_scope_ms"].values()])})
    return results


def compare(rows):
    lookup = {tuple(r[k] for k in ("dataset", "chunker", "query_id", "k", "backend")): r for r in rows}
    output = []
    for r in rows:
        if r["no_answer"] or r["backend"] not in ("fts5", "bm25s"):
            continue
        for control in ("dense_raw", "dense_eligible", "fts5"):
            if control == r["backend"]:
                continue
            key = tuple(r[k] for k in ("dataset", "chunker", "query_id", "k")) + (control,)
            before = lookup[key]
            delta = r["metrics"]["evidence_coverage"] - before["metrics"]["evidence_coverage"]
            if delta:
                output.append({k: r[k] for k in ("dataset", "chunker", "query_id", "k", "backend", "language", "cross_language", "multi_document")} |
                              {"control": control, "delta": delta, "before": before["metrics"]["evidence_coverage"], "after": r["metrics"]["evidence_coverage"]})
    return output


def export(report, output):
    summaries = []
    for r in report["summary"]:
        summaries.append({k: v for k, v in r.items() if not isinstance(v, dict)} |
                         {"search_median_of_scope_medians_ms": r["scope_search_p50_ms"]["median"],
                          "search_median_of_scope_p95_ms": r["scope_search_p95_ms"]["median"]})
    queries = [{k: r[k] for k in ("dataset", "chunker", "query_id", "backend", "k", "language", "cross_language", "multi_document", "no_answer")} |
               {"atom_coverage": r["metrics"]["evidence_coverage"], "document_recall": r["metrics"]["document_recall"],
                "complete_evidence": r["metrics"]["complete_evidence"], "returned": len(r["hits"]),
                "ids": ";".join(h["id"] for h in r["hits"])} for r in report["rows"]]
    for suffix, values in (("-summary.csv", summaries), ("-queries.csv", queries)):
        with output.with_name(output.stem.removesuffix("-summary") + suffix).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    return {k: v for k, v in report.items() if k != "rows"} | {"row_count": len(report["rows"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "benchmark", "resources", "resource", "export", "architecture", "native-image"))
    parser.add_argument("--previous-stress", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--backend", choices=("fts5", "bm25s", "dense"))
    parser.add_argument("--index-path", type=Path)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "native-image":
        result = native_image_probe()
    elif args.phase == "architecture":
        result = architecture()
    elif args.phase == "prepare":
        if not args.previous_stress:
            parser.error("--previous-stress required")
        result = prepare(args.previous_stress)
    else:
        if not args.input:
            parser.error("--input required")
        data = read(args.input)
        if args.phase == "benchmark":
            if args.repeats < 1:
                parser.error("--repeats must be positive")
            result = benchmark(data, args.repeats)
        elif args.phase == "resources":
            result = {"resources": resource_probes(data)}
        elif args.phase == "resource":
            if not args.backend or not args.index_path:
                parser.error("resource requires --backend and --index-path")
            result = measure_resource(data, args.backend, args.index_path)
        else:
            result = export(data, args.output)
    write(args.output, result)
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
