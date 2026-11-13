"""Experimental scope-local RRF. No runtime wiring or dual-index synchronization."""
from copy import deepcopy
from dataclasses import dataclass, field
import math
import sqlite3
from typing import Callable, Mapping, Sequence

from laew.rag.lexical_experiment import Binding, Hit


@dataclass(frozen=True)
class Ranking:
    binding: Binding
    hits: Sequence[Hit]


@dataclass(frozen=True)
class FusedHit:
    record: dict
    score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None


@dataclass
class Fusion:
    hits: list[FusedHit]
    union: list[FusedHit]
    diagnostics: dict = field(default_factory=dict)


def eligible_ranking(ranking: Ranking, binding: Binding, authorized: Mapping[str, dict], backend: str):
    """Authorize/validate before ranks are assigned; compact duplicates/filtered hits.

    The caller supplies the existing policy's canonical authorized records for ONE
    fresh corpus/scope/project. This registry is never inferred from query labels.
    Matching payloads are required, so stale lexical text cannot replace a dense
    chunk sharing its slot ID. Generation coordination remains Task 3 work.
    """
    if ranking.binding != binding:
        raise ValueError("Ranking binding mismatch")
    if backend not in ("dense", "fts5"):
        raise ValueError("Unknown backend")
    if len(ranking.hits) > 512:
        raise ValueError("Ranking exceeds experimental 512-hit bound")
    kept, seen = [], set()
    rejected = {"unauthorized": 0, "native_score_gate": 0, "duplicate": 0}
    for hit in ranking.hits:
        r = hit.record
        if r["source"] != binding.scope:
            raise ValueError("Hit escaped bound scope")
        if not math.isfinite(hit.score):
            raise ValueError("Nonfinite backend score")
        if backend == "dense" and not -1.000001 <= hit.score <= 1.000001:
            raise ValueError("Invalid cosine score")
        canonical = authorized.get(r["id"])
        if canonical is None:
            rejected["unauthorized"] += 1
            continue
        if canonical["source"] != binding.scope:
            raise ValueError("Authorized registry escaped scope")
        if any(r[k] != canonical[k] for k in ("id", "text", "source", "path", "metadata")):
            raise ValueError("Index payload mismatch: freshness/generation must be resolved before fusion")
        if (backend == "dense" and hit.score < .3) or (backend == "fts5" and hit.score >= 0):
            rejected["native_score_gate"] += 1
            continue
        if r["id"] in seen:
            rejected["duplicate"] += 1
            continue
        seen.add(r["id"])
        kept.append(Hit({k: canonical[k] for k in ("id", "text", "source", "path", "metadata")}, hit.score))
    return kept, rejected


def fuse(dense: Ranking, lexical: Ranking | None, *, authorized: Mapping[str, dict],
         final_limit: int = 10, constant: int = 60, lexical_error: str | None = None) -> Fusion:
    """Equal-weight sum(1/(constant + rank)), one-based eligible unique ranks.

    Original backend scores are retained, never added or compared. Fused score
    ties use chunk ID. Unavailable lexical retrieval preserves exact eligible
    dense order/scores, including ties; an empty lexical ranking is not an error.
    O((D+L) log(D+L)) work and O(D+L) retained output, with bounded inputs.
    """
    if not isinstance(final_limit, int) or not 0 <= final_limit <= 128:
        raise ValueError("Final limit must be an integer in [0,128]")
    if not isinstance(constant, int) or constant <= 0:
        raise ValueError("RRF constant must be a positive integer")
    binding = dense.binding
    d, d_rejected = eligible_ranking(dense, binding, authorized, "dense")
    l, l_rejected = eligible_ranking(lexical, binding, authorized, "fts5") if lexical is not None else ([], {})
    by_id = {}
    for backend, hits in (("dense", d), ("lexical", l)):
        for rank, hit in enumerate(hits, 1):
            entry = by_id.setdefault(hit.record["id"], {"record": hit.record, "score": 0.})
            entry["score"] += 1 / (constant + rank)
            entry[backend + "_rank"] = rank
            entry[backend + "_score"] = hit.score
    if lexical is None:
        # A real degraded-mode fallback is dense-only, not a renamed fusion score.
        union = [FusedHit(deepcopy(h.record), h.score, dense_score=h.score, dense_rank=i)
                 for i, h in enumerate(d, 1)]
    else:
        union = [FusedHit(**deepcopy(entry)) for entry in by_id.values()]
        union.sort(key=lambda h: (-h.score, h.record["id"]))
    return Fusion(union[:final_limit], union, {
        "constant": constant, "dense_raw": len(dense.hits), "lexical_raw": len(lexical.hits) if lexical is not None else None,
        "dense_eligible": len(d), "lexical_eligible": len(l), "union_before_truncation": len(union),
        "final_limit": final_limit, "returned": min(final_limit, len(union)),
        "dense_rejected": d_rejected, "lexical_rejected": l_rejected,
        "lexical_status": "unavailable" if lexical is None else "available" if l else "empty",
        "dense_fallback": lexical is None, "lexical_error": lexical_error,
    })


def retrieve(dense_search: Callable[[], Ranking], lexical_search: Callable[[], Ranking], *,
             authorized: Mapping[str, dict], final_limit=10) -> Fusion:
    """Dense failure and binding/payload errors surface; only availability degrades."""
    dense = dense_search()
    try:
        lexical = lexical_search()
    except (sqlite3.OperationalError, OSError) as error:
        return fuse(dense, None, authorized=authorized, final_limit=final_limit,
                    lexical_error=f"{type(error).__name__}: {error}")
    return fuse(dense, lexical, authorized=authorized, final_limit=final_limit)
