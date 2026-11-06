"""Run the frozen Global RAG retrieval baseline with the manifest embedding model."""
import argparse
import hashlib
import json
import math
import shutil
import tempfile
import time
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

from laew.manifest import load_manifest
from laew.rag.config import manifest_global_exclusions
from laew.rag.knowledge_base import KnowledgeBase, KnowledgeScope
from laew.rag.pipeline import RAGPipeline
from laew.runtime import build_embedding_service

TOP_K = 5
CONFIG_VERSION = "vector-only-2b.1"
DEFAULT_DATASET = Path("tests/rag/baseline_v1")


def document_id(chunk):
    alias = "@knowledge" if chunk.source == "global" else "@project"
    return alias + "/" + chunk.file_path.replace("\\", "/")


def score_query(query, chunks, known_sources):
    """Score returned evidence and unique documents in first-hit order."""
    ids = list(dict.fromkeys(document_id(chunk) for chunk, _ in chunks))[:TOP_K]
    scope = query["allowed_scope"]
    allowed = {"project", "global"} if scope == "hybrid" else {scope}
    result = {
        "ranked_documents": ids,
        "source_correctness": (sum(source in known_sources for source in ids) / len(ids) if ids else None),
        "scope_isolated": all(chunk.source in allowed for chunk, _ in chunks),
    }
    if query["no_answer"]:
        return result | {"no_answer_empty": not chunks}
    labels = query["relevance"]
    required = set(query["expected_document_ids"])
    hits = required.intersection(ids)
    ranks = [i for i, source in enumerate(ids, 1) if labels.get(source, 0) > 0]

    def dcg(grades):
        return sum((2 ** grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades, 1))

    evidence = query["evidence"]
    missing_evidence = [item for item in evidence if not any(
        document_id(chunk) == item["document_id"]
        and ("section" not in item or chunk.metadata.get("section_header") == item["section"])
        and " ".join(item["passage"].split()) in " ".join(chunk.text.split())
        for chunk, _ in chunks
    )]
    return result | {
        f"recall_at_{TOP_K}": len(hits) / len(required),
        f"precision_at_{TOP_K}": len(ranks) / TOP_K,
        "reciprocal_rank": 1 / ranks[0] if ranks else 0.0,
        f"ndcg_at_{TOP_K}": dcg([labels.get(source, 0) for source in ids]) / dcg(sorted(labels.values(), reverse=True)[:TOP_K]),
        "evidence_coverage": 1 - len(missing_evidence) / len(evidence),
        "missing_evidence": missing_evidence,
        "all_required_documents": hits == required,
        "complete_evidence": not missing_evidence,
    }


def summarize(rows):
    metrics = (f"recall_at_{TOP_K}", f"precision_at_{TOP_K}", "reciprocal_rank", f"ndcg_at_{TOP_K}",
               "evidence_coverage", "source_correctness", "scope_isolated",
               "all_required_documents", "complete_evidence", "no_answer_empty", "estimated_context_tokens", "returned_chunks")
    averages = {}
    for metric in metrics:
        values = [row[metric] for row in rows if row.get(metric) is not None]
        if values:
            averages["mrr" if metric == "reciprocal_rank" else metric] = sum(values) / len(values)
    return {"query_count": len(rows), **averages}


def evaluate(pipeline, dataset, known_sources):
    rows = []
    groups = defaultdict(list)
    for query in dataset["queries"]:
        result = pipeline.retrieve(query["text"], KnowledgeScope(query["allowed_scope"]), top_k=TOP_K)
        if result.error:
            raise RuntimeError(f"Retrieval failed for {query['id']}: {result.error}")
        row = {"id": query["id"], **score_query(query, result.chunks, known_sources),
               "estimated_context_tokens": getattr(result, "total_tokens", 0),
               "returned_chunks": len(result.chunks),
               "returned_evidence": [{"id": c.chunk_id, "document": document_id(c), "score": score, "text": c.text} for c, score in result.chunks]}
        rows.append(row)
        if query.get("split"):
            groups["split:" + query["split"]].append(row)
        groups[f"language:{query['language']}"].append(row)
        groups[f"phenomenon:{query['phenomenon']}"].append(row)
        if query["no_answer"]:
            groups["no_answer"].append(row)
        document_languages = dataset.get("document_languages", {})
        if any(document_languages.get(source) not in (None, query["language"])
               for source in query["expected_document_ids"]):
            groups["cross_language"].append(row)
    return {"overall": summarize(rows), "categories": {key: summarize(group) for key, group in sorted(groups.items())},
            "queries": rows}


def run(manifest_path, dataset_root, strategy="legacy"):
    import chromadb

    started = time.perf_counter()
    manifest = load_manifest(manifest_path)
    embedding = build_embedding_service(manifest)
    # Fail before any indexing if the configured endpoint cannot serve its declared dimensions.
    embedding.embed("LAEW synthetic embedding availability check")
    raw = (dataset_root / "dataset.json").read_text(encoding="utf-8").encode("utf-8")
    dataset = json.loads(raw)
    pipeline_config = manifest.get("rag", {}).get("pipeline", {})
    with tempfile.TemporaryDirectory(prefix="laew-rag-baseline-") as directory:
        root = Path(directory)
        for scope in ("project", "global"):
            shutil.copytree(dataset_root / scope, root / scope)
        client = chromadb.PersistentClient(path=str(root / "chroma"))
        try:
            # The only Chroma client used by this runner is the disposable local database.
            with patch("laew.rag.vector_store._build_chroma_client", return_value=client):
                kb = KnowledgeBase(str(root / "project"), str(root / "global"), embedding,
                    vector_store_config={"enabled": True, "global_collection": "laew_baseline_fixture"},
                    chunking_strategy=strategy,
                    global_source_exclusions=manifest_global_exclusions(manifest))
                prepare_started = time.perf_counter()
                prepared = [c for scope, folder in (("global", "global"), ("project", "project"))
                            for path in (root / folder).rglob("*.md")
                            for c in kb._load_file(path, scope, root / folder, embed=False)]
                prepare_seconds = time.perf_counter() - prepare_started
                index_started = time.perf_counter()
                kb.synchronize()
                index_seconds = time.perf_counter() - index_started
                indexed = kb.global_store.sync_records("global")
                project_count = len(kb.project_store.sync_records("project"))
                sizes = sorted(len(item.text) for item in indexed)
                pipeline = RAGPipeline(kb, embedding, top_k=TOP_K,
                    max_context_tokens=int(pipeline_config.get("max_context_tokens", 8000)),
                    similarity_threshold=float(pipeline_config.get("similarity_threshold", 0.3)))
                sources = {"@" + alias + "/" + path.relative_to(root / scope).as_posix()
                           for scope, alias in (("global", "knowledge"), ("project", "project"))
                           for path in (root / scope).rglob("*.md")}
                report = evaluate(pipeline, dataset, sources)
                index_bytes = sum(p.stat().st_size for p in (root / "chroma").rglob("*") if p.is_file())
        finally:
            # Release SQLite handles before removing the temporary database on Windows.
            close = getattr(client, "close", None)
            if close is not None:
                close()
    return {
        "dataset_name": dataset["id"], "dataset_version": dataset["version"],
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "corpus_sha256": {path.relative_to(dataset_root).as_posix(): hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                          for path in sorted(dataset_root.rglob("*.md"))},
        "embedding_model": embedding.model, "embedding_endpoint": embedding.base_url,
        "embedding_dimensions": embedding.dimensions, "chroma_version": version("chromadb"),
        "retrieval_config_version": CONFIG_VERSION, "top_k": TOP_K,
        "similarity_threshold": pipeline.similarity_threshold, "max_context_tokens": pipeline.max_context_tokens,
        "chunking": {"strategy": strategy, "size": kb.chunk_size, "overlap": kb.chunk_overlap if strategy == "legacy" else 0,
                     "global_chunk_count": len(sizes), "mean_chars": sum(sizes) / len(sizes) if sizes else 0,
                     "project_chunk_count": project_count, "embedding_count_both_scopes": len(sizes) + project_count,
                     "max_chars": max(sizes, default=0), "sizes_chars": sizes,
                     "index_seconds_both_scopes": index_seconds, "prepare_seconds": prepare_seconds,
                     "small_chunks_under_64": sum(n < 64 for n in sizes),
                     "oversize_chunks": sum(n > kb.chunk_size for n in sizes),
                     "synthetic_chars": sum(c.metadata.get("synthetic_chars", 0) for c in prepared),
                     "indexed_chars": sum(len(c.text) for c in prepared),
                     "index_bytes": index_bytes},
        "duration": time.perf_counter() - started, **report,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/SYSTEM_MANIFEST.yaml"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strategy", choices=("legacy", "structure-v1", "structure-v2"), default="legacy")
    parser.add_argument("--top-k", type=int, choices=(1, 5), default=5)
    args = parser.parse_args()
    global TOP_K
    TOP_K = args.top_k
    result = run(args.manifest, args.dataset, args.strategy)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
