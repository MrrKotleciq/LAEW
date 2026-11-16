"""Bounded, model-free context packing. Evaluation only; no runtime callers.

Inputs are authorized native candidates, their original cosine, the query and
ordinary source metadata. No corpus lookup, labels, scorer or answer is used.
Whole bodies are retained. Lexical novelty is a packing proxy, not entailment.
"""
from __future__ import annotations

from dataclasses import replace
import math
import re

from laew.rag.evidence_selection import (
    Candidate, Selection, SelectionConfig, SEPARATOR, _allocate_scopes, select,
)
from laew.rag.pipeline import RAGPipeline


VERSION = 'complementary-pack-v2'
VERSIONS = ('complementary-pack-v1', VERSION)
SETTINGS = dict(max_candidates=10, shingle_words=3, lexical_scale=100,
                source_weight=.10, section_weight=.10, query_weight=.20,
                discovery_metadata_removed=['tags', 'backlinks'], threshold=.3)


def words(text):
    return re.findall(r'\w+', text.casefold())


def shingles(text):
    values = words(text)
    width = min(SETTINGS['shingle_words'], len(values))
    return {tuple(values[i:i + width]) for i in range(len(values) - width + 1)} if width else set()


def bitsets(sets):
    """Represent lexical sets exactly as Python integers, without hashing loss."""
    ids = {value: i for i, value in enumerate(sorted(set().union(*sets)))} if sets else {}
    return [sum(1 << ids[value] for value in values) for values in sets]


def source_key(chunk):
    # Identity is local to an already authorized scope. Never collapse languages,
    # products or versions by filename stems, headings or textual resemblance.
    return chunk.source, chunk.file_path


def section_key(chunk):
    path = chunk.metadata.get('section_path')
    if not path:
        path = [chunk.metadata.get('section_header') or '']
    return source_key(chunk), tuple(path)


def _pack(candidates, scope, config, query, version):
    if version not in VERSIONS:
        raise ValueError('Unknown complementary selector version')
    if config.policy != 'ranked_fill':
        raise ValueError('Complementary packing requires the ranked_fill baseline')
    if len(candidates) > SETTINGS['max_candidates']:
        raise ValueError('Complementary packing supports native K10 only')
    if len(query) > 100_000:
        raise ValueError('Query character bound exceeded')
    if any(c.relevance is not None for c in candidates):
        raise ValueError('Original dense cosine only; no external reranker')
    # Reuse all eligibility, scope, identity, size and finite-score validation.
    baseline = select(candidates, scope, config)
    eligible = sorted((c for c in candidates if c.cosine >= config.threshold and c.chunk.text),
                      key=lambda c: -c.cosine)
    if not eligible or not baseline.chunks:
        return baseline
    originals = {c.chunk.chunk_id: c.chunk for c in eligible}
    if any(chunk.text != originals[chunk.chunk_id].text for chunk, _ in baseline.chunks):
        # A clipped baseline has no whole-fragment anchor. Keep it verbatim;
        # never make a new isolated prefix or silently expand its procedure.
        return baseline
    projected = [Candidate(replace(c.chunk, metadata={k: v for k, v in c.chunk.metadata.items()
                  if k not in SETTINGS['discovery_metadata_removed']}), c.cosine) for c in eligible]
    renderer = RAGPipeline(None, None, max_context_tokens=config.max_total_chars)
    rendered = [renderer._build_context([(c.chunk, c.cosine)])[0] for c in projected]
    costs = [len(value) for value in rendered]
    features = bitsets([shingles(c.chunk.text) for c in projected])
    query_words = set(words(query))
    query_features = bitsets([query_words] + [set(words(c.chunk.text)) & query_words for c in projected])[1:]
    source_keys = [source_key(c.chunk) for c in projected]
    section_keys = [section_key(c.chunk) for c in projected]
    # V1 anchors only the strongest body. V2 preserves ALL baseline bodies,
    # including unrecognized prerequisites and warnings. No keyword inference.
    mandatory_ids = ({chunk.chunk_id for chunk, _ in baseline.chunks}
                     if version == 'complementary-pack-v2' else {baseline.chunks[0][0].chunk_id})
    mandatory = sum(1 << i for i, c in enumerate(projected) if c.chunk.chunk_id in mandatory_ids)
    best_mask, best_key = 0, (-math.inf, 0, 0)
    costs_dp = [0] * (1 << len(projected))
    # For each feature, credit the greatest original cosine among selected
    # carriers. No feature is counted twice. All metadata grouping is scope-local.
    score_order = sorted(range(len(projected)), key=lambda i: -projected[i].cosine)
    for mask in range(1, 1 << len(projected)):
        bit = mask & -mask
        i = bit.bit_length() - 1
        rest = mask ^ bit
        cost = costs_dp[rest] + costs[i] + (len(SEPARATOR) if rest else 0)
        costs_dp[mask] = cost
        if mask & mandatory != mandatory or cost > config.budget * 4:
            continue
        covered = query_covered = 0
        lexical = 0.
        docs, sections = {}, {}
        for j in score_order:
            if mask & (1 << j):
                cosine = projected[j].cosine
                lexical += (features[j] & ~covered).bit_count() * cosine
                covered |= features[j]
                query_covered |= query_features[j]
                docs[source_keys[j]] = max(docs.get(source_keys[j], 0.), cosine)
                sections[section_keys[j]] = max(sections.get(section_keys[j], 0.), cosine)
        utility = (lexical / SETTINGS['lexical_scale']
                   + SETTINGS['source_weight'] * sum(docs.values())
                   + SETTINGS['section_weight'] * sum(sections.values())
                   + SETTINGS['query_weight'] * query_covered.bit_count() / max(1, len(query_words)))
        key = utility, -cost, -mask
        if key > best_key:
            best_mask, best_key = mask, key
    if not best_mask:
        return baseline
    chosen = [(c.chunk, c.cosine) for i, c in enumerate(projected) if best_mask & (1 << i)]
    context, used, estimated = RAGPipeline(None, None, max_context_tokens=config.budget)._build_context(chosen)
    if len(used) != len(chosen) or any(c.text != originals[c.chunk_id].text for c, _ in used):
        raise AssertionError('Whole-fragment packing/renderer disagreement')
    selected_ids = {c.chunk_id for c, _ in used}
    decisions = [dict(id=c.chunk.chunk_id, reason='selected' if c.chunk.chunk_id in selected_ids else
                      'ineligible' if c.cosine < config.threshold or not c.chunk.text else 'joint_budget_utility',
                      mandatory=c.chunk.chunk_id in mandatory_ids) for c in candidates]
    return Selection(context, used, estimated, decisions)


def select_complementary_scopes(pools, config: SelectionConfig, query='', overall_budget=8000,
                                version=VERSION):
    """Same fixed scope allocator as historical B/C; no cross-scope ranking."""
    return _allocate_scopes(pools, overall_budget,
        lambda scope, candidates, budget: _pack(candidates, scope,
            replace(config, budget=min(config.budget, budget)), query, version))
