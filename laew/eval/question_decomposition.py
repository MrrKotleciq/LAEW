"""Question-only development mechanism; no reference or retrieval dependencies.

Conservative focus decomposition retains the entire question as scope. It does
not infer hidden dependencies. This module has no production caller or I/O.
"""
from __future__ import annotations

import re

VERSION = 'explicit-question-focus-v1'
MAX_FOCI = 4
# Only syntax and generic interrogatives; no products, versions or task facts.
WH = r'(?:how|what|which|when|why|whether|where|jak|co|jakie|jaki|jakich|kiedy|czy|gdzie|dlaczego|wie|was|welche\w*|wann|warum|ob|wo)'
BOUNDARY = re.compile(
    rf'[?;\n]+\s*|,?\s+\b(?:and|or|i|oraz|lub|und|oder)\s+(?={WH}\b)|,\s+(?={WH}\b)',
    re.IGNORECASE,
)


def decompose(question: str) -> dict:
    """Split explicit information requests; retain all original scope verbatim.

    Sentences before the first interrogative stay in scope. At most four
    contiguous groups are formed; excess clauses are grouped, never dropped.
    An unsplittable question performs its original search only. The original
    query is always retained in the multi-query search plan.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError('A nonempty original question is required')
    pieces = [p.strip(' ,;?\n') for p in BOUNDARY.split(question) if p.strip(' ,;?\n')]
    requests = []
    for piece in pieces:
        match = re.search(rf'(?<!\w){WH}\b', piece, re.IGNORECASE)
        if match:
            requests.append(piece[match.start():])
        elif requests:
            # A continuation may be an enumerated operation or condition.
            requests[-1] += '; ' + piece
    if len(requests) < 2:
        return dict(version=VERSION, question=question, foci=[], queries=[question],
                    status='unsplit', limitations=['Implicit dependencies are not inferred'])
    if len(requests) > MAX_FOCI:
        requests = ['; '.join(requests[i * len(requests) // MAX_FOCI:
                                      (i + 1) * len(requests) // MAX_FOCI])
                    for i in range(MAX_FOCI)]
    queries = list(dict.fromkeys([question] + [question + '\nRequested part: ' + p for p in requests]))
    return dict(version=VERSION, question=question, foci=requests, queries=queries,
                status='split', limitations=[
                    'Implicit dependencies are not inferred',
                    'Interrogative detection can mistake embedded clauses for requests',
                    'Retaining full scope may dilute the focused embedding',
                    'Conditions remain in full scope but are not semantically attached to a focus'])


def search_allocations(query_count: int, total: int) -> list[int]:
    """Equal total raw search-result budget, including the original query."""
    if not 1 <= query_count <= total:
        raise ValueError('Each query needs at least one candidate slot')
    return [total // query_count + (i < total % query_count) for i in range(query_count)]


def merge_ranked(searches: list[list[dict]], total: int, threshold: float = .3) -> dict:
    """Stable round robin; chunk identity deduplication; no learned fusion.

    Search lists must already respect search_allocations. No refill search is
    allowed, so duplicates can leave fewer than total unique candidates.
    Same-text chunks from distinct source identities are never collapsed.
    """
    seen, merged, duplicates, filtered = set(), [], [], []
    for rank in range(max(map(len, searches), default=0)):
        for query_index, results in enumerate(searches):
            if rank >= len(results):
                continue
            candidate = results[rank]
            key = candidate['id']
            if candidate['cosine'] < threshold:
                filtered.append((query_index, rank, key))
            elif key in seen:
                duplicates.append((query_index, rank, key))
            else:
                seen.add(key)
                merged.append(dict(candidate, query_index=query_index, query_rank=rank + 1))
    return dict(candidates=merged[:total], duplicates=duplicates, filtered=filtered)
