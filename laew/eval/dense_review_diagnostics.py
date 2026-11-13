"""Task 3A inspection only: cached cosine ranks, metadata and oracle query probes.

No retriever, expansion policy, parent index, fusion or source mutation is built.
The only optional inference is six fixed requests to the existing local embedder.
"""
import argparse
from collections import defaultdict
import math
from pathlib import Path
import time
from urllib.parse import urlparse

import numpy as np

from laew.eval.lexical_benchmark import digest, hydrate, read, write
from laew.eval.reranker_benchmark import atom_present


def normalized(vectors):
    result = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(result, axis=-1, keepdims=True)
    if not np.all(np.isfinite(result)) or np.any(norms == 0):
        raise ValueError("Invalid cached embedding")
    return result / norms


def atom_ranks(query, records, scores):
    order = np.argsort(-scores, kind="stable")
    return [next((rank for rank, i in enumerate(order, 1) if atom_present(a, hydrate(records[int(i)]))), None)
            for a in query["evidence"]]


def inspect(corpus, retrieval, oracle_embeddings=False):
    if corpus["content_hash"] != digest(corpus["conditions"]) or retrieval["corpus_hash"] != corpus["content_hash"]:
        raise ValueError("Cache provenance mismatch")
    lookup = {(r["dataset"], r["chunker"], r["query_id"]): r for r in retrieval["rows"]
              if r["backend"] == "dense_eligible" and r["k"] == 10}
    groups, rows, s14 = [], [], []
    for condition in corpus["conditions"]:
        name, chunker = condition["dataset_directory"], condition["chunking"]["strategy"]
        docs = defaultdict(list)
        for r in condition["chunks"]:
            docs[r["source"], r["path"]].append(r)
        for item in condition["queries"]:
            q = item["query"]
            if q["no_answer"]:
                continue
            seeds = lookup[name, chunker, q["id"]]["hits"]
            seeded_docs = {(h["source"], h["path"]) for h in seeds}
            document_order = {}
            for scope in ("global", "project"):
                document_order[scope] = list(dict.fromkeys(h["path"].replace("\\", "/") for h in seeds if h["source"] == scope))
            v = normalized(item["embedding"])
            atoms = []
            for a in q["evidence"]:
                alias, path = a["document_id"].split("/", 1)
                key = ("global" if alias == "@knowledge" else "project", path.replace("/", "\\"))
                # Current fixtures are Windows-captured, with simple paths. Use
                # normalized logical path identity rather than guessing IDs.
                candidates = next((rs for (scope, stored), rs in docs.items()
                                   if scope == key[0] and stored.replace("\\", "/") == path), [])
                scores = normalized([r["embedding"] for r in candidates]) @ v if candidates else []
                within = atom_ranks({"evidence": [a]}, candidates, scores)[0] if candidates else None
                seeded = any(scope == key[0] and stored.replace("\\", "/") == path for scope, stored in seeded_docs)
                atoms.append({"document": a["document_id"], "document_seeded_at_10": seeded,
                              "document_first_hit_rank_in_scope": document_order[key[0]].index(path) + 1 if path in document_order[key[0]] else None,
                              "document_chunks": len(candidates), "within_document_rank": within})
            rows.append({"dataset": name, "chunker": chunker, "query_id": q["id"], "atoms": atoms,
                         "all_required_documents_seeded": all(a["document_seeded_at_10"] for a in atoms),
                         "all_atoms_within_own_doc_10": all(a["within_document_rank"] and a["within_document_rank"] <= 10 for a in atoms),
                         "interpretation": "Structural opportunity audit only; no documents routed or expanded, no output selection."})
            if q["id"] != "s14":
                continue
            records = [r for r in condition["chunks"] if r["source"] == "global"]
            matrix = normalized([r["embedding"] for r in records])
            scores = matrix @ v
            order = np.argsort(-scores, kind="stable")
            rank_by_id = {records[int(i)]["id"]: rank for rank, i in enumerate(order, 1)}
            atlas = [r for r in records if r["path"] == "atlas.md"]
            atlas_order = sorted(atlas, key=lambda r: rank_by_id[r["id"]])
            file_order = sorted(atlas, key=lambda r: (r["metadata"].get("start_offset", r["metadata"].get("section_index", 0)),
                                                     r["metadata"].get("chunk_index", 0)))
            position = {r["id"]: i for i, r in enumerate(file_order)}
            seed = records[int(order[0])]
            evidence = []
            for a in q["evidence"]:
                matches = [r for r in atlas if atom_present(a, hydrate(r))]
                match = min(matches, key=lambda r: rank_by_id[r["id"]])
                index = next(i for i, r in enumerate(records) if r["id"] == match["id"])
                outrank = [r for i, r in enumerate(records) if r["path"] != "atlas.md" and scores[i] > scores[index]]
                evidence.append({"passage": a["passage"], "id": match["id"], "text": match["text"], "metadata": match["metadata"],
                                 "cosine": float(scores[index]), "global_rank": rank_by_id[match["id"]],
                                 "within_atlas_rank": next(i for i, r in enumerate(atlas_order, 1) if r["id"] == match["id"]),
                                 "non_atlas_chunks_outranking": len(outrank),
                                 "file_order_distance_from_top_hit": abs(position[match["id"]] - position[seed["id"]]) if seed["id"] in position else None})
            s14.append({"dataset": name, "chunker": chunker, "query": q["text"], "atlas_chunks": len(atlas),
                        "top_hit": {"id": seed["id"], "path": seed["path"], "cosine": float(scores[int(order[0])])},
                        "evidence": evidence, "top_non_atlas": [{"id": records[int(i)]["id"], "cosine": float(scores[int(i)]),
                            "text": records[int(i)]["text"]} for i in order if records[int(i)]["path"] != "atlas.md"][:3],
                        "cached_atom_ranks": atom_ranks(q, records, scores)})
        matched = [r for r in rows if r["dataset"] == name and r["chunker"] == chunker]
        groups.append({"dataset": name, "chunker": chunker, "answerable": len(matched),
                       "all_docs_seeded_at_10": sum(r["all_required_documents_seeded"] for r in matched),
                       "all_atoms_local_rank_le_10": sum(r["all_atoms_within_own_doc_10"] for r in matched),
                       "max_document_chunks": max(map(len, docs.values())),
                       "metadata_keys": sorted({k for r in condition["chunks"] for k in r["metadata"]})})
    stress = next(c for c in corpus["conditions"] if c["dataset_directory"] == "stress_1036")
    q14 = next(i for i in stress["queries"] if i["query"]["id"] == "s14")
    q16 = next(i for i in stress["queries"] if i["query"]["id"] == "s16")
    matrix = normalized([r["embedding"] for r in stress["chunks"]])
    cached_oracle = {"label": "ORACLE: reuse independently phrased frozen s16 as a known acceptance facet; not automatic decomposition",
                     "query": q16["query"]["text"], "s14_atom_ranks": atom_ranks(q14["query"], stress["chunks"], matrix @ normalized(q16["embedding"]))}
    parent_text = Path("tests/rag/evidence_supplement_v1/global/atlas.md").read_text(encoding="utf-8")
    from laew.rag.pipeline import RAGPipeline
    from laew.rag.vector_store import DocumentChunk
    parent = DocumentChunk("budget-inspection-only", parent_text, source="global", file_path="atlas.md")
    context, used, token_count = RAGPipeline(None, None, max_context_tokens=1000)._build_context([(parent, .8)])
    parent_budget = {"label": "Hypothetical one-parent renderer inspection, NOT a parent retriever implementation",
                     "source_chars": len(parent_text), "raw_estimated_tokens": math.ceil(len(parent_text) / 4),
                     "rendered_tokens_at_1000": token_count, "truncated": bool(used and used[0][0].text != parent_text),
                     "atoms_visible": [any(atom_present(a, c) for c, _ in used) for a in q14["query"]["evidence"]]}
    required = [r for r in stress["chunks"] if any(atom_present(a, hydrate(r)) for a in q14["query"]["evidence"])]
    _, required_used, required_tokens = RAGPipeline(None, None, max_context_tokens=1000)._build_context([(hydrate(r), .8) for r in required])
    parent_budget["oracle_labeled_fragments_only"] = {"label": "ORACLE context-cost lower bound using known labels, not a selector",
        "count": len(required_used), "estimated_tokens": required_tokens,
        "atoms_visible": [any(atom_present(a, c) for c, _ in required_used) for a in q14["query"]["evidence"]]}
    oracles = {"status": "not_requested", "rows": []}
    if oracle_embeddings:
        from laew.manifest import load_manifest
        from laew.runtime import build_embedding_service
        embedder = build_embedding_service(load_manifest("manifests/SYSTEM_MANIFEST.yaml"))
        if urlparse(embedder.base_url).hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Only the existing local embedding endpoint is allowed")
        if embedder.model != corpus["embedding_model"] or embedder.dimensions != corpus["dimensions"]:
            raise ValueError("Embedding configuration differs from frozen cache")
        probes = [
            ("fresh_original_control", q14["query"]["text"]),
            ("ORACLE_pl_prerequisite", "Co zabezpieczyć przed aktualizacją firmware Atlas?"),
            ("ORACLE_pl_acceptance", "Jakie dwa wyniki muszą znaleźć się w odbiorze Atlas?"),
            ("ORACLE_en_compound_translation", "What should I secure before updating the Atlas firmware, and which two results must be recorded in its acceptance test?"),
            ("ORACLE_en_prerequisite", "What should I secure before updating the Atlas firmware?"),
            ("ORACLE_en_acceptance", "Which two results must be recorded in the Atlas acceptance test?"),
        ]
        try:
            control = None
            for label, text in probes:
                started = time.perf_counter()
                vector = normalized(embedder.embed(text))
                elapsed = (time.perf_counter() - started) * 1000
                if control is None:
                    control = float(vector @ normalized(q14["embedding"]))
                    if control < .999:
                        raise ValueError("Fresh query control does not align with cached embedding space")
                oracles["rows"].append({"label": label, "text": text, "embedding_ms_single": elapsed,
                                       "s14_atom_ranks": atom_ranks(q14["query"], stress["chunks"], matrix @ vector)})
            oracles.update(status="measured", control_cosine=control, endpoint=embedder.base_url, model=embedder.model)
        except Exception as error:
            oracles.update(status="unavailable_or_partial", error=f"{type(error).__name__}: {error}")
    return {"task": "3A review diagnostics only", "corpus_hash": corpus["content_hash"], "new_indexes": 0,
            "new_retrieval_methods": 0, "groups": groups, "structural_audit": rows, "s14": s14,
            "cached_oracle": cached_oracle, "manual_oracle_probes": oracles, "parent_budget_inspection": parent_budget}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--oracle-embeddings", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(read(args.corpus), read(args.retrieval), args.oracle_embeddings)
    write(args.output, result)
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
