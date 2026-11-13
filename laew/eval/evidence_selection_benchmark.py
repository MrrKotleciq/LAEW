"""Isolated Stage 2B.2 model-free selector experiment; no runtime integration."""
import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import asdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import tempfile
import time
import tracemalloc
from unittest.mock import patch

from laew.eval import rag_baseline as baseline
from laew.eval.reranker_benchmark import (
    atom_present, chunk_data, digest, percentile, rank_metrics, replay, restore,
)
from laew.manifest import load_manifest
from laew.rag.evidence_selection import (
    Candidate, POLICIES, SelectionConfig, overlap, select, select_scopes, tokens,
)
from laew.rag.knowledge_base import KnowledgeScope
from laew.runtime import build_embedding_service, context_budget_from_manifest


def read(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def verify(pool):
    if pool["candidate_pool_hash"] != digest(pool["conditions"]):
        raise ValueError("Frozen candidate pool changed")
    if pool.get("cosine_threshold") != .3:
        raise ValueError("Unexpected eligibility threshold")


def collect(pipeline, dataset, sources):
    """Capture separate real K2/5/10/20 fixture searches, never production stores."""
    rows = []
    kb = pipeline.knowledge_base
    all_chunks = [c for scope, store in (("global", kb.global_store), ("project", kb.project_store))
                  for c in store.sync_records(scope)]
    for query in dataset["queries"]:
        embedding_started = time.perf_counter()
        vector = pipeline.embedding_service.embed(query["text"])
        embedding_ms = (time.perf_counter() - embedding_started) * 1000
        scopes = ("project", "global") if query["allowed_scope"] == "hybrid" else (query["allowed_scope"],)
        records = []
        for scope in scopes:
            store = kb.global_store if scope == "global" else kb.project_store
            chunks, pools, timings = {}, {}, {}
            for k in (2, 5, 10, 20):
                started = time.perf_counter()
                pairs = pipeline._retrieve_candidates(vector, KnowledgeScope(scope), min(k, store.count()))
                timings[str(k)] = (time.perf_counter() - started) * 1000
                if any(c.source != scope for c, _ in pairs):
                    raise RuntimeError("Fixture scope isolation failed")
                pools[str(k)] = [c.chunk_id for c, _ in pairs]
                chunks.update({c.chunk_id: chunk_data(c, score) for c, score in pairs})
            records.append({"scope": scope, "chunks": list(chunks.values()), "pools": pools,
                            "retrieval_ms": timings, "available_index_chunks": store.count()})
        rows.append({"query": query, "scopes": records, "embedding_ms": embedding_ms,
                     "index_evidence_available": [any(atom_present(e, c) for c in all_chunks) for e in query["evidence"]]})
        print(f"Captured {query['id']}", flush=True)
    return {"queries": rows, "sources": sorted(sources), "document_languages": dataset.get("document_languages", {})}


def prepare_supplement():
    root = Path("tests/rag/evidence_supplement_v1")
    frozen = read(root / "FREEZE.json")
    for name, expected in frozen["sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Supplement changed after label freeze")
    conditions = []
    for strategy in ("legacy", "structure-v2"):
        with patch.object(baseline, "evaluate", collect):
            report = baseline.run(Path("manifests/SYSTEM_MANIFEST.yaml"), root, strategy)
        report["dataset_directory"] = root.name
        conditions.append(report)
    return {"conditions": conditions, "candidate_pool_hash": digest(conditions), "cosine_threshold": .3,
            "label_freeze": frozen, "protocol": "evidence-selection-v1"}


def pairs_for(scope, k):
    lookup = {c["id"]: c for c in scope["chunks"]}
    ids = scope["pools"].get(str(k))
    if ids is None:
        if k != 5:
            raise ValueError("Missing captured K")
        ids = scope["pools"]["10"][:5]
    return [(restore(lookup[i]), lookup[i]["cosine"]) for i in ids]


def distribution(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values),
            "p95": percentile(values, .95), "max": max(values)} if values else None


def analyze(pools, overall_budget=8000):
    for pool in pools:
        verify(pool)
    # Staged K sweep at 1000, then budget sweep at K20; no huge Cartesian grid.
    settings = [(k, 1000) for k in (5, 10, 20)] + [(20, b) for b in (500, 2000, 5000)]
    rows = []
    for pool in pools:
        for condition in pool["conditions"]:
            for item in condition["queries"]:
                query = item["query"]
                for k, budget in settings:
                    raw = {s["scope"]: pairs_for(s, k) for s in item["scopes"]}
                    raw_pairs = [p for pairs in raw.values() for p in pairs]
                    eligible_pairs = [p for p in raw_pairs if p[1] >= .3]
                    candidate_metric = rank_metrics(query, raw_pairs)
                    eligible_metric = rank_metrics(query, eligible_pairs)
                    candidates = {scope: [Candidate(c, score) for c, score in pairs] for scope, pairs in raw.items()}
                    for policy in POLICIES:
                        config = SelectionConfig(policy=policy, budget=budget)
                        started = time.perf_counter()
                        results, context = select_scopes(candidates, config, overall_budget)
                        selection_ms = (time.perf_counter() - started) * 1000
                        selected = [p for result in results.values() for p in result.chunks]
                        final = rank_metrics(query, selected)
                        received, system_tokens = replay(query, [(s, r.context) for s, r in results.items()])
                        if not received:
                            raise RuntimeError("Context lost in adapter replay")
                        stages = []
                        for index, atom in enumerate(query["evidence"]):
                            if not candidate_metric["evidence_positions"][index]:
                                stage = "absent_from_candidates"
                            elif not eligible_metric["evidence_positions"][index]:
                                stage = "filtered_by_original_cosine_threshold"
                            elif final["evidence_positions"][index]:
                                stage = "delivered_to_adapter"
                            else:
                                hits = {c.chunk_id for c, _ in eligible_pairs if atom_present(atom, c)}
                                reasons = {d["reason"] for r in results.values() for d in r.decisions if d["id"] in hits}
                                stage = ("removed_by_context_budget" if "budget" in reasons or "selected" in reasons
                                         else "selection_limit" if "selection_limit" in reasons else "low_marginal_utility")
                            stages.append({"atom": index, "document": atom["document_id"], "stage": stage,
                                           "available_in_index": item["index_evidence_available"][index]})
                        relevant = {d for d, grade in query["relevance"].items() if grade > 0}
                        lexical = [tokens(c.text) for c, _ in selected]
                        originals = {(c.source, c.chunk_id): c.text for c, _ in raw_pairs}
                        unconstrained = {s: select(cs, s, config) for s, cs in candidates.items()}
                        fragments = [{"id": c.chunk_id, "scope": c.source, "document": baseline.document_id(c),
                                      "metadata": c.metadata, "cosine": score,
                                      "truncated": c.text != originals[(c.source, c.chunk_id)]} for c, score in selected]
                        rows.append({"dataset": condition["dataset_directory"], "chunker": condition["chunking"]["strategy"],
                            "query_id": query["id"], "topic_id": query.get("topic_id", query["id"]),
                            "policy": policy, "k": k, "budget": budget, "no_answer": bool(query["no_answer"]),
                            "language": query["language"], "multi_document": len(query["expected_document_ids"]) > 1,
                            "candidate": candidate_metric, "eligible": eligible_metric, "final": final, "stages": stages,
                            "per_scope": {s: {"candidate_count": len(raw[s]), "eligible_count": sum(score >= .3 for _, score in raw[s]),
                                              "selected_count": len(r.chunks), "estimated_tokens": r.estimated_tokens,
                                              "decisions": r.decisions} for s, r in results.items()},
                            "fragments": fragments, "selection_ms_single_observation": selection_ms,
                            "document_count": len({baseline.document_id(c) for c, _ in selected}),
                            "scope_count": len({c.source for c, _ in selected}), "fragment_count": len(selected),
                            "overlapping_fragments": sum(any(overlap(lexical[i], previous) >= .8 for previous in lexical[:i]) for i in range(len(lexical))),
                            "irrelevant_documents_fragments": sum(baseline.document_id(c) not in relevant for c, _ in selected),
                            "no_labeled_atom_fragments": sum(not any(atom_present(a, c) for a in query["evidence"]) for c, _ in selected),
                            "context_tokens": math.ceil(len(context) / 4), "context_chars": len(context),
                            "unconstrained_fragment_tokens": sum(r.estimated_tokens for r in unconstrained.values()),
                            "allocation_dropped_fragments": sum(len(r.chunks) for r in unconstrained.values()) - len(selected),
                            "serialized_system_tokens": system_tokens, "overall_allocation": overall_budget,
                            "allocation_compliant": math.ceil(len(context) / 4) <= overall_budget,
                            "adapter_received": received,
                            "retrieval_ms_historical_or_single": {s["scope"]: s["retrieval_ms"].get(str(k)) for s in item["scopes"]},
                            "k5_is_captured_search": all("5" in s["pools"] for s in item["scopes"])})
            print(f"Analyzed {condition['dataset_directory']}/{condition['chunking']['strategy']}", flush=True)
    return {"protocol": "evidence-selection-v1", "pool_hashes": [p["candidate_pool_hash"] for p in pools],
            "config": asdict(SelectionConfig()), "overall_budget": overall_budget,
            "rows": rows, "summary": summarize(rows), "regressions": comparisons(rows)}


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in ("dataset", "chunker", "policy", "k", "budget"))].append(row)
    result = []
    for key, group in sorted(groups.items()):
        answered = [r for r in group if not r["no_answer"]]
        multi = [r for r in answered if r["multi_document"]]
        no_answer = [r for r in group if r["no_answer"]]
        mean = lambda values: statistics.mean(values) if values else None
        fragments = sum(r["fragment_count"] for r in group)
        delivered_atoms = sum(s["stage"] == "delivered_to_adapter" for r in answered for s in r["stages"])
        cost = sum(r["context_tokens"] for r in answered)
        result.append(dict(zip(("dataset", "chunker", "policy", "k", "budget"), key)) | {
            "query_count": len(group), "answerable": len(answered),
            "candidate_recall": mean([r["candidate"]["document_recall"] for r in answered]),
            "candidate_coverage": mean([r["candidate"]["evidence_coverage"] for r in answered]),
            "eligible_coverage": mean([r["eligible"]["evidence_coverage"] for r in answered]),
            "coverage": mean([r["final"]["evidence_coverage"] for r in answered]),
            "complete": mean([r["final"]["complete_evidence"] for r in answered]),
            "multi_document_coverage": mean([r["final"]["evidence_coverage"] for r in multi]),
            "multi_document_complete": mean([r["final"]["complete_evidence"] for r in multi]),
            "no_answer_empty": mean([r["final"]["no_answer_empty"] for r in no_answer]),
            "context_tokens": distribution([r["context_tokens"] for r in group]),
            "fragment_count": distribution([r["fragment_count"] for r in group]),
            "document_count": distribution([r["document_count"] for r in group]),
            "selection_ms_single_observation": distribution([r["selection_ms_single_observation"] for r in group]),
            "irrelevant_fragment_rate": sum(r["irrelevant_documents_fragments"] for r in group) / fragments if fragments else 0,
            "no_labeled_atom_rate": sum(r["no_labeled_atom_fragments"] for r in group) / fragments if fragments else 0,
            "overlap_rate": sum(r["overlapping_fragments"] for r in group) / fragments if fragments else 0,
            "atoms_per_1000_estimated_tokens": delivered_atoms * 1000 / cost if cost else None,
            "loss_stages": dict(Counter(s["stage"] for r in group for s in r["stages"])),
            "truncated_fragments": sum(f["truncated"] for r in group for f in r["fragments"]),
            "allocation_dropped_fragments": sum(r["allocation_dropped_fragments"] for r in group),
            "allocation_compliant": all(r["allocation_compliant"] for r in group),
            "adapter_received": all(r["adapter_received"] for r in group)})
    return result


def comparisons(rows):
    """Per-query paired changes; no independence or significance claim."""
    controls = {tuple(r[k] for k in ("dataset", "chunker", "k", "budget", "query_id")): r
                for r in rows if r["policy"] == "top2"}
    output = []
    for r in rows:
        if r["policy"] == "top2" or r["no_answer"]:
            continue
        key = tuple(r[k] for k in ("dataset", "chunker", "k", "budget", "query_id"))
        old = controls[key]
        delta = r["final"]["evidence_coverage"] - old["final"]["evidence_coverage"]
        if delta:
            output.append({k: r[k] for k in ("dataset", "chunker", "k", "budget", "query_id", "policy", "multi_document")} |
                          {"coverage_delta": delta, "before": old["final"]["evidence_coverage"],
                           "after": r["final"]["evidence_coverage"], "context_delta": r["context_tokens"] - old["context_tokens"]})
    return output


def performance(pool, repeats=30):
    verify(pool)
    outputs = []
    for condition in pool["conditions"]:
        if condition["dataset_directory"] != "hard_cases_v1":
            continue
        item = next(i for i in condition["queries"] if i["query"]["id"] == "h03")
        scope = item["scopes"][0]
        for k in (5, 10, 20, 128):
            pairs = pairs_for(scope, min(k, 20))
            candidates = [Candidate(c, score) for c, score in pairs]
            if k == 128:
                from dataclasses import replace
                candidates = [Candidate(replace(pairs[i % len(pairs)][0], chunk_id=f"stress-{i}",
                                              text=pairs[i % len(pairs)][0].text + f"\nDiagnostic {i}"),
                                        pairs[i % len(pairs)][1]) for i in range(k)]
            for policy in POLICIES:
                config = SelectionConfig(policy=policy, budget=1000)
                select(candidates, scope["scope"], config)
                samples = []
                for _ in range(repeats):
                    started = time.perf_counter()
                    select(candidates, scope["scope"], config)
                    samples.append((time.perf_counter() - started) * 1000)
                tracemalloc.start()
                select(candidates, scope["scope"], config)
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                outputs.append({"chunker": condition["chunking"]["strategy"], "k": k, "actual_candidates": len(candidates),
                                "policy": policy, "wall_ms": distribution(samples), "samples_ms": samples,
                                "python_peak_allocated_bytes": peak, "synthetic_expansion": k == 128})
    return {"selector_performance": outputs, "repeats": repeats, "memory_method": "tracemalloc separate probe; excludes native and pre-existing allocations"}


def scale(count=1024, repeats=20):
    """Real local embeddings, isolated Chroma; distractors are stress data only."""
    import chromadb
    from laew.rag.vector_store import ChromaVectorStore, DocumentChunk
    manifest = load_manifest("manifests/SYSTEM_MANIFEST.yaml")
    embedding = build_embedding_service(manifest)
    dataset_root = Path("tests/rag/evidence_supplement_v1")
    # Use the normal chunker to retain a realistic evidence-bearing long manual.
    from laew.rag.knowledge_base import KnowledgeBase
    kb = KnowledgeBase(str(dataset_root / "project"), str(dataset_root / "global"), embedding,
                       vector_store_config={"enabled": False})
    evidence_chunks = kb._load_file(dataset_root / "global/atlas.md", "global", dataset_root / "global", embed=False)
    topics = ["storage queue", "clock synchronization", "firmware recovery", "build artifacts", "transaction snapshots",
              "connector inspection", "data acquisition", "network telemetry", "sensor calibration", "release validation",
              "checksum verification", "event triggers", "database checkpoints", "sample buffering", "cable shielding", "audit records"]
    chunks = list(evidence_chunks)
    for i in range(count):
        topic, other = topics[i % len(topics)], topics[(i // len(topics)) % len(topics)]
        text = (f"Synthetic distractor engineering record {i}. Subsystem {topic}, review area {other}. "
                f"Device group {i // 16} schedules inspection after {i % 29 + 1} operating cycles. "
                f"This fixture discusses maintenance logging, reference measurements and test preparation. "
                f"Record {i} supplies no Atlas firmware prerequisites or acceptance limits. "
                f"Its numeric tracking value is {i * 17 + 3} and its channel group is {i % 64}.")
        chunks.append(DocumentChunk(f"stress-{i}", text, source="global", file_path=f"stress/{i}.md"))
    embedding_started = time.perf_counter()
    for offset in range(0, len(chunks), 16):
        batch = chunks[offset:offset + 16]
        vectors = embedding.embed_batch([c.text for c in batch])
        for c, vector in zip(batch, vectors):
            c.embedding = vector
        if offset % 128 == 0:
            print(f"Stress embedded {offset + len(batch)}/{len(chunks)}", flush=True)
    embedding_seconds = time.perf_counter() - embedding_started
    queries = [q for q in read(dataset_root / "dataset.json")["queries"] if q["topic_id"] == "atlas"]
    with tempfile.TemporaryDirectory(prefix="laew-selection-scale-") as directory:
        client = chromadb.PersistentClient(path=str(Path(directory) / "chroma"))
        try:
            with patch("laew.rag.vector_store._build_chroma_client", return_value=client):
                store = ChromaVectorStore(collection_name="selection_stress", embedding_model_id="fixture-stress")
                started = time.perf_counter()
                store.add_chunks(chunks)
                indexing_seconds = time.perf_counter() - started
                rows = []
                for query in queries:
                    vector = embedding.embed(query["text"])
                    for k in (2, 5, 10, 20):
                        store.search(vector, top_k=k)
                        samples = []
                        for _ in range(repeats):
                            started = time.perf_counter()
                            pairs = store.search(vector, top_k=k)
                            samples.append((time.perf_counter() - started) * 1000)
                        eligible = [(c, score) for c, score in pairs if score >= .3]
                        selected = {}
                        for policy in POLICIES:
                            result = select([Candidate(c, score) for c, score in pairs], "global", SelectionConfig(policy=policy, budget=1000))
                            selected[policy] = {"metrics": rank_metrics(query, result.chunks), "count": len(result.chunks),
                                                "tokens": result.estimated_tokens}
                        rows.append({"query_id": query["id"], "no_answer": bool(query["no_answer"]), "k": k,
                                     "retrieval_ms": distribution(samples), "samples_ms": samples,
                                     "candidate": rank_metrics(query, pairs), "eligible": rank_metrics(query, eligible),
                                     "eligible_count": len(eligible), "selection": selected})
                index_bytes = sum(p.stat().st_size for p in Path(directory).rglob("*") if p.is_file())
        finally:
            client.close()
    return {"diagnostic_only": True, "synthetic_distractors": count, "evidence_chunks": len(evidence_chunks),
            "total_chunks": len(chunks), "dimensions": embedding.dimensions, "model": embedding.model,
            "corpus_hash": digest([c.to_dict() for c in chunks]), "embedding_seconds": embedding_seconds,
            "indexing_seconds": indexing_seconds, "index_bytes": index_bytes, "rows": rows,
            "limitations": "One generated distractor corpus, one legacy evidence document, four related questions; not independent relevance labels or million-document scaling."}


def exact_tokens(pool):
    """Optional non-generating tokenizer probe; content tokens, not chat template."""
    import requests
    verify(pool)
    manifest = load_manifest("manifests/SYSTEM_MANIFEST.yaml")
    providers = manifest["agent"]["llm"]["providers"]
    server = next(p for p in providers if p["type"] == "llama.cpp")
    endpoint = f"http://{server['host']}:{server['port']}/tokenize"
    observations = []
    try:
        model = requests.get(endpoint.rsplit("/", 1)[0] + "/v1/models", timeout=5).json()
        for condition in pool["conditions"]:
            for item in condition["queries"]:
                query = item["query"]
                # A fixed full-dataset sample: each K20/1000 policy, both chunkers.
                candidates = {s["scope"]: [Candidate(c, score) for c, score in pairs_for(s, 20)] for s in item["scopes"]}
                for policy in POLICIES:
                    _, context = select_scopes(candidates, SelectionConfig(policy=policy, budget=1000))
                    response = requests.post(endpoint, json={"content": context, "add_special": False}, timeout=10)
                    response.raise_for_status()
                    values = response.json()["tokens"]
                    observations.append({"query_id": query["id"], "chunker": condition["chunking"]["strategy"], "policy": policy,
                                         "estimated": math.ceil(len(context) / 4), "exact_content_tokens": len(values)})
        return {"status": "measured", "endpoint": endpoint, "model": model, "rows": observations,
                "boundary": "Rendered RAG context content only, add_special=false; excludes chat template/system/history/tools."}
    except (requests.RequestException, ValueError, KeyError) as error:
        return {"status": "unavailable_or_partial", "endpoint": endpoint, "error": str(error), "rows": observations}


def export(report, output):
    """Readable sidecars; full provenance/decisions remain in the gzip artifact."""
    summary_rows = []
    for row in report["summary"]:
        flat = {k: v for k, v in row.items() if not isinstance(v, dict)}
        for field in ("context_tokens", "fragment_count", "document_count", "selection_ms_single_observation"):
            flat.update({field + "_" + k: v for k, v in row[field].items()})
        summary_rows.append(flat)
    query_rows = []
    for row in report["rows"]:
        query_rows.append({k: row[k] for k in ("dataset", "chunker", "query_id", "topic_id", "policy", "k", "budget", "no_answer", "multi_document", "fragment_count", "document_count", "context_tokens", "serialized_system_tokens", "allocation_compliant")} |
                          {"candidate_coverage": row["candidate"]["evidence_coverage"], "eligible_coverage": row["eligible"]["evidence_coverage"],
                           "final_coverage": row["final"]["evidence_coverage"], "complete": row["final"]["complete_evidence"],
                           "selected_ids": ";".join(f["id"] for f in row["fragments"]),
                           "loss_stages": ";".join(s["stage"] for s in row["stages"])})
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix, rows in (("-summary.csv", summary_rows), ("-queries.csv", query_rows)):
        with output.with_name(output.stem + suffix).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return {k: v for k, v in report.items() if k != "rows"} | {
        "row_count": len(report["rows"]), "adapter_replays_received": sum(r["adapter_received"] for r in report["rows"]),
        "overall_allocation_violations": sum(not r["allocation_compliant"] for r in report["rows"]),
        "maximum_rendered_rag_tokens": max(r["context_tokens"] for r in report["rows"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare-supplement", "analyze", "performance", "scale", "tokenize", "export"))
    parser.add_argument("--input", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--distractors", type=int, default=1024)
    args = parser.parse_args()
    if args.repeats < 1 or not 64 <= args.distractors <= 4096:
        parser.error("repeats >= 1 and 64 <= distractors <= 4096 required")
    if args.phase == "prepare-supplement":
        result = prepare_supplement()
    elif args.phase == "scale":
        result = scale(args.distractors, args.repeats)
    else:
        if not args.input:
            parser.error("--input required")
        pools = [read(p) for p in args.input]
        if args.phase == "export":
            result = export(pools[0], args.output)
        elif args.phase == "analyze":
            budget = context_budget_from_manifest(load_manifest("manifests/SYSTEM_MANIFEST.yaml"))
            result = analyze(pools, budget.rag)
        elif args.phase == "performance":
            result = performance(pools[0], args.repeats)
        else:
            result = exact_tokens(pools[0])
    write(args.output, result)
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
