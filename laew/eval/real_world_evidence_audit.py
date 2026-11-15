"""Offline source-span diagnostics; never changes the historical scorer or labels.

Refinements are explicit, agent-reviewed source excerpts, not an automatic
semantic judge. A partial-character score is only a triage signal.
"""
from __future__ import annotations

import copy
import hashlib
from statistics import mean

from laew.eval.real_world_retrieval import score_stage, span_present, union


def visible_fraction(span, coverage, texts):
    """Count unique visible non-whitespace source characters, including gaps."""
    text = texts[span['source_id']]
    start, end = span['start'], span['end']
    if not 0 <= start < end <= len(text):
        raise ValueError('Invalid source offsets')
    total = sum(not char.isspace() for char in text[start:end])
    if not total:
        raise ValueError('Whitespace-only evidence is not a fact')
    ranges = union(coverage.get(span['source_id'], []))
    visible = sum(
        sum(not char.isspace() for char in text[max(start, a):min(end, z)])
        for a, z in ranges if max(start, a) < min(end, z)
    )
    return visible / total


def refine_label(label, spans, texts, refinements):
    """Replace a fact's parent span by conjunctive, hash-pinned subspans.

    Original coherent alternative sets, fact statements, and applicability stay
    fixed. Each replacement must be within its original source/version span.
    Semantic sufficiency is a recorded review judgment, never inferred here.
    """
    label = copy.deepcopy(label)
    spans = copy.deepcopy(spans)
    used = set()
    created = set()
    for fact in label.get('required_answer_facts', []):
        for alternative in fact['evidence_alternatives']:
            for parent in list(alternative):
                key = fact['id'] + '/' + parent
                if key not in refinements:
                    continue
                spec = refinements[key]
                if not spec.get('rationale') or spec.get('origin') != 'agent':
                    raise ValueError('Refinement needs explicit agent review provenance')
                original = spans[parent]
                text = texts[original['source_id']]
                if hashlib.sha256(text.encode()).hexdigest() != spec['normalized_sha256']:
                    raise ValueError('Refinement source/version hash mismatch')
                if not spec['segments']:
                    raise ValueError('Empty refinement cannot earn credit')
                ids = []
                for index, segment in enumerate(spec['segments']):
                    a, z = segment['start'], segment['end']
                    if not original['start'] <= a < z <= original['end']:
                        raise ValueError('Refinement escapes its parent source span')
                    value = text[a:z]
                    if (not value.strip() or hashlib.sha256(value.encode()).hexdigest()
                            != segment['text_sha256']):
                        raise ValueError('Refinement excerpt changed or is empty')
                    sid = f'diagnostic:{key}:{index}'
                    if sid in spans and sid not in created:
                        raise ValueError('Duplicate diagnostic span identity')
                    spans[sid] = dict(original, id=sid, start=a, end=z, text=value)
                    created.add(sid)
                    ids.append(sid)
                alternative[alternative.index(parent):alternative.index(parent) + 1] = ids
                # Keep parent membership, plus only its own fact-specific atoms.
                for evidence_set in label['minimal_sufficient_evidence_sets']:
                    if parent in evidence_set:
                        evidence_set.extend(s for s in ids if s not in evidence_set)
                used.add(key)
    relevant = {key for key in refinements if key.split('/')[0] in {
        fact['id'] for fact in label.get('required_answer_facts', [])}}
    if used != relevant:
        raise ValueError('Refinement refers to an unused fact/parent alternative')
    return label, spans


def diagnose(label, spans, texts, coverage, refinements=None, warning_ids=()):
    original = score_stage(label, spans, coverage, texts, warning_ids)
    revised, atoms = refine_label(label, spans, texts, refinements or {})
    refined = score_stage(revised, atoms, coverage, texts, warning_ids)
    partial = {}
    if label['positive_evidence_recall_applicable']:
        for fact in label['required_answer_facts']:
            alternatives = []
            for alternative in fact['evidence_alternatives']:
                if not any(set(alternative) <= set(s) for s in
                           label['minimal_sufficient_evidence_sets']):
                    continue
                alternatives.append(dict(
                    spans=alternative,
                    fractions={s: visible_fraction(spans[s], coverage, texts)
                               for s in alternative},
                    full=all(span_present(spans[s], coverage, texts) for s in alternative),
                ))
            partial[fact['id']] = alternatives
    return dict(original=original, diagnostic=refined, partial_spans=partial,
                interpretation='Post-result agent diagnostic; not independent semantic validation')


def summarize(rows):
    """Preserve unsupported N/A and separate original and diagnostic counts."""
    result = {}
    for split in ('pilot', 'sealed'):
        for arm in ('A', 'B', 'C'):
            items = [r for r in rows if r['split'] == split and r['arm'] == arm]
            if not items:
                continue
            summary = {}
            for stage in ('raw', 'eligible', 'selected'):
                summary[stage] = {}
                for metric in ('original', 'diagnostic'):
                    applicable = [r[stage][metric] for r in items
                                  if r[stage][metric]['fact_recall'] is not None]
                    summary[stage][metric] = dict(
                        answerable=len(applicable),
                        fact_recall=mean(r['fact_recall'] for r in applicable) if applicable else None,
                        complete=sum(r['complete'] for r in applicable) if applicable else None,
                    )
            result[split + '/' + arm] = summary
    return result
