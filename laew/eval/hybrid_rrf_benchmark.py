"""Task 2: isolated cached RRF quality and fresh local retrieval timing."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import csv
import hashlib
import math
from pathlib import Path
import statistics
import tempfile
import time
import tracemalloc

from laew.eval.lexical_benchmark import read, write, digest, hydrate, stats
from laew.eval.reranker_benchmark import scoped_ranking_metrics, replay
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_ranked_scopes, select_scopes
from laew.rag.lexical_experiment import Binding, Hit
from laew.rag.rrf_experiment import Ranking, FusedHit, eligible_ranking, fuse, retrieve

SETTINGS = ((5, 5), (10, 10), (20, 20), (50, 50), (20, 10), (50, 10))
METHODS = ("dense", "fts5", "rrf")


def verify(corpus, retrieval):
    if corpus["content_hash"] != digest(corpus["conditions"]):
        raise ValueError("Corpus cache changed")
    if retrieval["corpus_hash"] != corpus["content_hash"]:
        raise ValueError("Rankings and corpus come from different captures")
    return {tuple(r[k] for k in ("dataset", "chunker", "query_id", "k", "backend")): r for r in retrieval["rows"]}


def registries(condition):
    return {scope: {r["id"]: {k: r[k] for k in ("id", "text", "source", "path", "metadata")}
                    for r in condition["chunks"] if r["source"] == scope} for scope in ("global", "project")}


def binding_for(condition, scope):
    return Binding(condition["dataset_directory"] + "/" + condition["chunking"]["strategy"], scope,
                   "fixture-project" if scope == "project" else None)


def cached_ranking(row, scope, binding, authorized):
    hits = []
    for h in row["hits"]:
        if h["source"] != scope:
            continue
        if h["id"] not in authorized or h["path"] != authorized[h["id"]]["path"]:
            raise ValueError("Capture identity does not match canonical authorized records")
        hits.append(Hit(authorized[h["id"]], h["score"]))
    return Ranking(binding, hits)


def metrics(query, pools, cutoff=None):
    return scoped_ranking_metrics(query, [(s, [(hydrate(h.record), h.score) for h in hs]) for s, hs in pools.items()], cutoff)


def pack(hit):
    return {"id": hit.record["id"], "source": hit.record["source"], "path": hit.record["path"],
            "metadata": hit.record["metadata"], "ranking_score": hit.score,
            "dense_score": hit.dense_score, "lexical_score": hit.lexical_score,
            "dense_rank": hit.dense_rank, "lexical_rank": hit.lexical_rank}


def analyze(corpus, retrieval, overall_budget=8000):
    lookup = verify(corpus, retrieval)
    rows, control_matches = [], 0
    config = SelectionConfig(policy="ranked_fill", budget=1000)
    for condition in corpus["conditions"]:
        registry = registries(condition)
        for item in condition["queries"]:
            q = item["query"]
            scopes = ("project", "global") if q["allowed_scope"] == "hybrid" else (q["allowed_scope"],)
            for depth, limit in SETTINGS:
                outputs = {method: {} for method in METHODS}
                backend_pools = {method: {} for method in METHODS}
                unions, diagnostics, timings = {}, {}, {}
                for scope in scopes:
                    key = (condition["dataset_directory"], condition["chunking"]["strategy"], q["id"], depth)
                    dense_row, lexical_row = lookup[key + ("dense_raw",)], lookup[key + ("fts5",)]
                    dense = cached_ranking(dense_row, scope, binding_for(condition, scope), registry[scope])
                    lexical = cached_ranking(lexical_row, scope, dense.binding, registry[scope])
                    d, _ = eligible_ranking(dense, dense.binding, registry[scope], "dense")
                    l, _ = eligible_ranking(lexical, dense.binding, registry[scope], "fts5")
                    d_hits = [FusedHit(h.record, h.score, dense_score=h.score, dense_rank=i) for i, h in enumerate(d, 1)]
                    l_hits = [FusedHit(h.record, h.score, lexical_score=h.score, lexical_rank=i) for i, h in enumerate(l, 1)]
                    started = time.perf_counter()
                    fusion = fuse(dense, lexical, authorized=registry[scope], final_limit=limit)
                    timings[scope] = {"fusion_ms_single_observation": (time.perf_counter() - started) * 1000,
                                      "task1_dense_ms": dense_row["timing_per_scope_ms"][scope],
                                      "task1_fts_ms": lexical_row["timing_per_scope_ms"][scope]}
                    for name, hits in (("dense", d_hits), ("fts5", l_hits), ("rrf", fusion.union)):
                        backend_pools[name][scope] = hits
                        outputs[name][scope] = hits[:limit]
                    unions[scope], diagnostics[scope] = fusion.union, fusion.diagnostics
                union_metrics = metrics(q, unions)
                relevant = {d for d, grade in q["relevance"].items() if grade > 0}
                for method in METHODS:
                    selected_pool = outputs[method]
                    candidate = metrics(q, selected_pool, limit)
                    own_pool = metrics(q, backend_pools[method])
                    row = {"dataset": condition["dataset_directory"], "chunker": condition["chunking"]["strategy"],
                           "query_id": q["id"], "language": q["language"], "topic_id": q.get("topic_id", q["id"]),
                           "method": method, "backend_depth": depth, "final_limit": limit, "no_answer": bool(q["no_answer"]),
                           "multi_document": len(q["expected_document_ids"]) > 1,
                           "cross_language": any(condition.get("document_languages", {}).get(d) not in (None, q["language"]) for d in q["expected_document_ids"]),
                           "union": union_metrics, "backend_pool": own_pool, "candidate": candidate,
                           "fusion_diagnostics": diagnostics, "processing_observation": timings,
                           "candidates_by_scope": {s: [pack(h) for h in hs] for s, hs in selected_pool.items()},
                           "union_count_by_scope": {s: len(hs) for s, hs in unions.items()},
                           "candidate_count_by_scope": {s: len(hs) for s, hs in selected_pool.items()},
                           "index_atom_available": item["index_atom_available"], "selection": None}
                    if limit == 10:
                        ranked_pairs = {s: [(hydrate(h.record), h.score) for h in hs] for s, hs in selected_pool.items()}
                        selected, context = select_ranked_scopes(ranked_pairs, config, overall_budget)
                        chosen = {s: [FusedHit({"id": c.chunk_id, "text": c.text, "source": c.source,
                                              "path": c.file_path, "metadata": c.metadata}, score)
                                      for c, score in r.chunks] for s, r in selected.items()}
                        final = metrics(q, chosen)
                        received, system_tokens = replay(q, [(s, r.context) for s, r in sorted(selected.items())])
                        if not received:
                            raise RuntimeError("Adapter lost selected evidence")
                        if method == "dense" and depth == 10:
                            old_pools = {s: [Candidate(c, score) for c, score in pairs] for s, pairs in ranked_pairs.items()}
                            old, old_context = select_scopes(old_pools, config, overall_budget)
                            if old_context != context or any(old[s].chunks != selected[s].chunks for s in selected):
                                raise RuntimeError("Primary dense selector control changed")
                            control_matches += 1
                        fragments = []
                        for s, result in selected.items():
                            originals = {h.record["id"]: h for h in selected_pool[s]}
                            for c, _ in result.chunks:
                                h = originals[c.chunk_id]
                                fragments.append(pack(h) | {"truncated": c.text != h.record["text"],
                                    "contains_labeled_atom": any(atom_match(a, c) for a in q["evidence"])})
                        used = [c for r in selected.values() for c, _ in r.chunks]
                        row["selection"] = {"metrics": final, "context_tokens": math.ceil(len(context) / 4),
                            "per_scope_tokens": {s: r.estimated_tokens for s, r in selected.items()},
                            "fragment_count": len(used), "fragments": fragments,
                            "document_count": len({document_id(c) for c in used}),
                            "irrelevant_fragments": sum(document_id(c) not in relevant for c in used),
                            "no_atom_fragments": sum(not f["contains_labeled_atom"] for f in fragments),
                            "truncated_fragments": sum(f["truncated"] for f in fragments),
                            "budget_dropped": sum(len(selected_pool[s]) - len(r.chunks) for s, r in selected.items()),
                            "overall_allocation": overall_budget, "allocation_compliant": math.ceil(len(context) / 4) <= overall_budget,
                            "adapter_received": received, "serialized_system_tokens": system_tokens,
                            "context_sha256": hashlib.sha256(context.encode()).hexdigest()}
                    row["atom_stages"] = []
                    for i, atom in enumerate(q["evidence"]):
                        if union_metrics["evidence_positions"][i] is None:
                            stage = "absent_from_eligible_union"
                        elif own_pool["evidence_positions"][i] is None:
                            stage = "absent_from_method_backend"
                        elif candidate["evidence_positions"][i] is None:
                            stage = "lost_at_final_candidate_limit"
                        elif row["selection"] is not None and row["selection"]["metrics"]["evidence_positions"][i] is None:
                            stage = "lost_at_context_budget"
                        else:
                            stage = "delivered_to_adapter" if row["selection"] is not None else "available_after_retrieval"
                        row["atom_stages"].append({"atom": i, "document": atom["document_id"], "stage": stage})
                    rows.append(row)
        print(f"Analyzed {condition['dataset_directory']}/{condition['chunking']['strategy']}", flush=True)
    return {"protocol": "hybrid-rrf-task2-v1", "corpus_hash": corpus["content_hash"], "rrf_constant": 60,
            "settings_depth_final": SETTINGS, "primary_dense_selector_controls_matched": control_matches,
            "rows": rows, "summary": summarize(rows), "comparisons": comparisons(rows)}


def atom_match(atom, chunk):
    from laew.eval.reranker_benchmark import atom_present
    return atom_present(atom, chunk)


def document_id(chunk):
    return ("@knowledge/" if chunk.source == "global" else "@project/") + chunk.file_path.replace(chr(92), "/")


def summarize(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in ("dataset", "chunker", "method", "backend_depth", "final_limit"))].append(r)
    result = []
    for key, group in sorted(groups.items()):
        answered = [r for r in group if not r["no_answer"]]
        mean = lambda values: statistics.mean(values) if values else None
        subsets = {"multi_document": [r for r in answered if r["multi_document"]],
                   "cross_language": [r for r in answered if r["cross_language"]]}
        subsets.update({"language_" + language: [r for r in answered if r["language"] == language] for language in {r["language"] for r in answered}})
        summary = dict(zip(("dataset", "chunker", "method", "backend_depth", "final_limit"), key)) | {
            "queries": len(group), "answerable": len(answered),
            "candidate_coverage": mean([r["candidate"]["evidence_coverage"] for r in answered]),
            "candidate_complete": mean([r["candidate"]["complete_evidence"] for r in answered]),
            "candidate_document_recall": mean([r["candidate"]["document_recall"] for r in answered]),
            "union_coverage": mean([r["union"]["evidence_coverage"] for r in answered]),
            "scope_union_count": stats([n for r in group for n in r["union_count_by_scope"].values()]),
            "scope_candidate_count": stats([n for r in group for n in r["candidate_count_by_scope"].values()]),
            "subsets": {name: {"n": len(subset), "candidate_coverage": mean([r["candidate"]["evidence_coverage"] for r in subset]),
                                "final_coverage": mean([r["selection"]["metrics"]["evidence_coverage"] for r in subset]) if key[-1] == 10 else None}
                        for name, subset in subsets.items()},
            "candidate_no_answer_empty": mean([not any(r["candidate_count_by_scope"].values()) for r in group if r["no_answer"]]),
            "loss_stages": dict(Counter(s["stage"] for r in group for s in r["atom_stages"])), "selection": None}
        if group[0]["selection"] is not None:
            total_fragments = sum(r["selection"]["fragment_count"] for r in group)
            summary["selection"] = {"coverage": mean([r["selection"]["metrics"]["evidence_coverage"] for r in answered]),
                "complete": mean([r["selection"]["metrics"]["complete_evidence"] for r in answered]),
                "tokens": stats([r["selection"]["context_tokens"] for r in group]),
                "fragments": stats([r["selection"]["fragment_count"] for r in group]),
                "irrelevant_rate": sum(r["selection"]["irrelevant_fragments"] for r in group) / max(1, total_fragments),
                "no_atom_rate": sum(r["selection"]["no_atom_fragments"] for r in group) / max(1, total_fragments),
                "truncated": sum(r["selection"]["truncated_fragments"] for r in group),
                "budget_dropped": sum(r["selection"]["budget_dropped"] for r in group),
                "allocation_compliant": all(r["selection"]["allocation_compliant"] for r in group),
                "adapter_received": all(r["selection"]["adapter_received"] for r in group)}
        result.append(summary)
    return result


def comparisons(rows):
    lookup = {tuple(r[k] for k in ("dataset", "chunker", "query_id", "backend_depth", "final_limit", "method")): r for r in rows}
    result = []
    for r in rows:
        if r["method"] == "dense" or r["no_answer"]:
            continue
        base = (r["dataset"], r["chunker"], r["query_id"])
        for label, control in (("dense_same_depth", lookup[base + (r["backend_depth"], r["final_limit"], "dense")]),
                               ("primary_dense10", lookup[base + (10, 10, "dense")])):
            if label == "primary_dense10" and r["final_limit"] != 10:
                continue
            for stage in ("candidate", "selection"):
                if stage == "selection" and r["selection"] is None:
                    continue
                old = control[stage] if stage == "candidate" else control[stage]["metrics"]
                new = r[stage] if stage == "candidate" else r[stage]["metrics"]
                gains = [i for i, (a, b) in enumerate(zip(old["evidence_positions"], new["evidence_positions"])) if a is None and b is not None]
                losses = [i for i, (a, b) in enumerate(zip(old["evidence_positions"], new["evidence_positions"])) if a is not None and b is None]
                worse = [i for i, (a, b) in enumerate(zip(old["evidence_positions"], new["evidence_positions"])) if a and b and b > a]
                if gains or losses or worse:
                    result.append({k: r[k] for k in ("dataset", "chunker", "query_id", "method", "backend_depth", "final_limit", "cross_language", "multi_document")} |
                                  {"control": label, "stage": stage, "before": old["evidence_coverage"], "after": new["evidence_coverage"],
                                   "recovered_atoms": gains, "lost_atoms": losses, "ranking_worse_atoms": worse})
    return result


def performance(corpus, repeats=20):
    from laew.eval.lexical_benchmark import DenseIndex, rss
    from laew.rag.lexical_experiment import FTS5Index
    if corpus["content_hash"] != digest(corpus["conditions"]):
        raise ValueError("Corpus cache changed")
    rows, resources = [], []
    with tempfile.TemporaryDirectory(prefix="laew-hybrid-perf-") as scratch:
        for condition in corpus["conditions"]:
            if condition["dataset_directory"] not in ("reranker_holdout_v1", "stress_1036") or condition["chunking"]["strategy"] != "legacy":
                continue
            records = [r for r in condition["chunks"] if r["source"] == "global"]
            authorized = registries(condition)["global"]
            binding = binding_for(condition, "global")
            dense = DenseIndex(Path(scratch) / (binding.corpus.replace("/", "-") + "-dense"), binding)
            dense.rebuild(records)
            dense.search(condition["queries"][0]["embedding"], 10)
            before = rss()
            path = Path(scratch) / (binding.corpus.replace("/", "-") + "-fts.db")
            started = time.perf_counter()
            lexical = FTS5Index(path, binding)
            lexical.rebuild(records)
            build_ms = (time.perf_counter() - started) * 1000
            after = rss()
            try:
                for item in condition["queries"]:
                    if item["query"]["allowed_scope"] != "global":
                        continue
                    for depth in (5, 10, 20, 50):
                        d_call = lambda: Ranking(binding, dense.search(item["embedding"], depth))
                        l_call = lambda: Ranking(binding, lexical.search(item["query"]["text"], depth))
                        d, l = d_call(), l_call()
                        operations = {
                            "dense": lambda: eligible_ranking(d_call(), binding, authorized, "dense")[0][:10],
                            "fts5": lambda: eligible_ranking(l_call(), binding, authorized, "fts5")[0][:10],
                            "fusion_only": lambda: fuse(d, l, authorized=authorized, final_limit=10),
                            "sequential_hybrid": lambda: retrieve(d_call, l_call, authorized=authorized, final_limit=10),
                        }
                        times = {}
                        for name, operation in operations.items():
                            operation()
                            samples = []
                            for _ in range(repeats):
                                started = time.perf_counter()
                                operation()
                                samples.append((time.perf_counter() - started) * 1000)
                            times[name] = stats(samples)
                        tracemalloc.start()
                        result = fuse(d, l, authorized=authorized, final_limit=10)
                        _, peak = tracemalloc.get_traced_memory()
                        tracemalloc.stop()
                        rows.append({"dataset": condition["dataset_directory"], "query_id": item["query"]["id"], "backend_depth": depth,
                                     "final_limit": 10, "timing_ms": times, "fusion_python_peak_bytes": peak,
                                     "union_count": len(result.union), "fallback": result.diagnostics["dense_fallback"]})
            finally:
                lexical.close()
                dense.close()
            resources.append({"dataset": condition["dataset_directory"], "rss_dense_warm": before, "rss_after_fts_build": after,
                              "fts_build_ms": build_ms, "fts_index_bytes": path.stat().st_size})
            print(f"Timed {condition['dataset_directory']}", flush=True)
    return {"repeats": repeats, "rows": rows, "resources": resources,
            "boundary": "Local cached-vector retrieval + validation/fusion; excludes query embedding and final selection. Fusion tracing is separate."}


def export(report, output):
    flat = []
    for r in report["rows"]:
        flat.append({k: r[k] for k in ("dataset", "chunker", "query_id", "method", "backend_depth", "final_limit", "language", "cross_language", "multi_document", "no_answer")} |
                    {"union_coverage": r["union"]["evidence_coverage"], "candidate_coverage": r["candidate"]["evidence_coverage"],
                     "candidate_complete": r["candidate"]["complete_evidence"],
                     "union_count": sum(r["union_count_by_scope"].values()), "candidate_count": sum(r["candidate_count_by_scope"].values()),
                     "final_coverage": r["selection"]["metrics"]["evidence_coverage"] if r["selection"] else None,
                     "final_complete": r["selection"]["metrics"]["complete_evidence"] if r["selection"] else None,
                     "tokens": r["selection"]["context_tokens"] if r["selection"] else None,
                     "fragments": r["selection"]["fragment_count"] if r["selection"] else None})
    with output.with_name(output.stem.removesuffix("-summary") + "-queries.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    return {k: v for k, v in report.items() if k != "rows"} | {"row_count": len(report["rows"]),
        "adapter_replays": sum(r["selection"] is not None for r in report["rows"]),
        "allocation_violations": sum(r["selection"] is not None and not r["selection"]["allocation_compliant"] for r in report["rows"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("analyze", "performance", "export"))
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--retrieval", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "export":
        result = export(read(args.input), args.output)
    else:
        corpus = read(args.corpus)
        if args.phase == "performance":
            result = performance(corpus, args.repeats)
        else:
            from laew.manifest import load_manifest
            from laew.runtime import context_budget_from_manifest
            result = analyze(corpus, read(args.retrieval), context_budget_from_manifest(load_manifest("manifests/SYSTEM_MANIFEST.yaml")).rag)
    write(args.output, result)
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
