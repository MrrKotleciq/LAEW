"""Experimental compact attribution, separate from production context delivery.

Only document discovery tags/backlinks are omitted from rendered attribution.
Source text, section paths, scope, type/status, ranking and budgets are fixed.
This module cannot read questions, benchmark labels, facts or scoring rubrics.
"""
from dataclasses import replace

from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes


MECHANISM_ID = 'compact-attribution-v1'
OMITTED_METADATA = frozenset({'tags', 'backlinks'})
VARIANTS = {'A-D1': ('A', 'legacy', 2, 'top2', 500),
            'B-D1': ('B', 'legacy', 10, 'ranked_fill', 1000),
            'C-D1': ('C', 'structure-v2', 10, 'ranked_fill', 1000)}


def select_compact_scopes(pools, config: SelectionConfig, overall_budget=8000):
    """Reuse the exact existing renderer/allocator with compact metadata copies.

    No new ranking, novelty penalty, quota, content extraction or truncation
    policy is introduced. Original candidate objects are never mutated.
    """
    if config.policy not in ('top2', 'ranked_fill'):
        raise ValueError('Compact attribution only wraps historical selection policies')
    projected = {
        scope: [Candidate(replace(c.chunk, metadata={
            key: value for key, value in c.chunk.metadata.items()
            if key not in OMITTED_METADATA}), c.cosine, c.relevance) for c in candidates]
        for scope, candidates in pools.items()
    }
    return select_scopes(projected, config, overall_budget)
