"""Evaluation-only, reviewed semantic requirements and source-proof scoring.

No natural-language model or heuristic paraphrase detector is used. A human or
disclosed agent supplies exhaustive, quote-bound semantic annotations. This
module validates those annotations, technical invariants and delivered source
proofs, and keeps correctness, completeness, safety and grounding separate.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib

from laew.eval.real_world_retrieval import span_present, union


CATEGORIES = {'essential', 'conditional', 'optional', 'alternative'}
UNITS = {
    'V': ('voltage', '1', '0'), 'kV': ('voltage', '1000', '0'),
    'A': ('current', '1', '0'), 'mA': ('current', '.001', '0'),
    'Hz': ('frequency', '1', '0'), 'kHz': ('frequency', '1000', '0'),
    'C': ('temperature', '1', '273.15'), 'K': ('temperature', '1', '0'),
    '%': ('ratio', '.01', '0'), 'fraction': ('ratio', '1', '0'),
    'day': ('time', '86400', '0'), 'hour': ('time', '3600', '0'),
    'mm': ('length', '.001', '0'), 'm': ('length', '1', '0'),
    'N m': ('torque', '1', '0'), 'mm3': ('volume', '1', '0'),
}


def canonical(value):
    """Compare reviewed meanings; allow equivalent units, never drop dimensions."""
    if isinstance(value, dict):
        if set(value) != {'value', 'unit'} or value['unit'] not in UNITS:
            raise ValueError('Unsupported structured quantity')
        dimension, factor, offset = UNITS[value['unit']]
        values = value['value'] if isinstance(value['value'], list) else [value['value']]
        return dimension, tuple(Decimal(str(v)) * Decimal(factor) + Decimal(offset)
                                for v in values)
    # bool must not compare equal to integer 0/1.
    return type(value).__name__, value


def validate_family(family, atoms):
    requirements = family['requirements']
    ids = [r['id'] for r in requirements]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Requirements must be nonempty and unique')
    conditions = set(family['conditions'])
    for requirement in requirements:
        if requirement['category'] not in CATEGORIES:
            raise ValueError('Unknown requirement category')
        if not set(requirement.get('when', {})) <= conditions:
            raise ValueError('Undeclared applicability condition')
        if requirement['category'] == 'conditional' and not requirement.get('when'):
            raise ValueError('Conditional requirement needs a trigger')
        if requirement['category'] == 'optional' and requirement['safety_critical']:
            raise ValueError('Applicable safety requirements cannot be optional')
        if requirement.get('contextual') and family['positive_recall_applicable']:
            raise ValueError('Answerable technical evidence cannot be waived as contextual')
        if not requirement.get('rationale'):
            raise ValueError('Requirement needs a technical justification')
        for alternative in requirement['proofs']:
            if not alternative or not set(alternative) <= set(atoms):
                raise ValueError('Invalid source proof alternative')
        for value in requirement.get('invariants', {}).values():
            canonical(value)
    for method in family['methods']:
        if not method['required'] or not set(method['required']) <= set(ids):
            raise ValueError('Invalid complete method')
        if not set(method.get('conditions', {})) <= conditions:
            raise ValueError('Unknown method condition')
        essential = {r['id'] for r in requirements if r['category'] == 'essential'}
        if not essential <= set(method['required']):
            raise ValueError('A complete method omits an essential requirement')
    if len({m['id'] for m in family['methods']}) != len(family['methods']):
        raise ValueError('Duplicate method identity')


def validate_atoms(atoms, texts, units):
    """Every atom binds exact frozen source/version and visible technical text."""
    for aid, atom in atoms.items():
        sid = atom['source_id']
        if sid not in texts or sid not in units or aid != atom['id']:
            raise ValueError('Unknown source or atom identity')
        unit, text = units[sid], texts[sid]
        if (atom['normalized_sha256'] != unit['normalized_sha256']
                or atom['revision'] != unit['revision']
                or hashlib.sha256(text.encode()).hexdigest() != atom['normalized_sha256']):
            raise ValueError('Source/version mismatch')
        start, end = atom['start'], atom['end']
        if not 0 <= start < end <= len(text):
            raise ValueError('Invalid atom offsets')
        value = text[start:end]
        if (not value.strip() or hashlib.sha256(value.encode()).hexdigest() != atom['text_sha256']
                or value != atom['text'] or '[Derived' in value
                or 'Visual information unavailable' in value):
            raise ValueError('Changed, derived or empty atom')
        if not atom.get('rationale') or not atom.get('original_location'):
            raise ValueError('Atom lacks source-grounded review provenance')


def applies(requirement, conditions):
    """Unknown applicability is unresolved; it is never silently waived."""
    unknown = False
    for key, expected in requirement.get('when', {}).items():
        if conditions.get(key) is None:
            unknown = True
        elif conditions[key] != expected:
            return False
    return None if unknown else True


def active_requirements(family, method, conditions):
    required = set(method['required'])
    active, unresolved = [], []
    for requirement in family['requirements']:
        if requirement['category'] == 'optional':
            continue
        activation = applies(requirement, conditions)
        if requirement['id'] in required or requirement['category'] == 'conditional':
            if activation is None:
                unresolved.append(requirement['id'])
            elif activation:
                active.append(requirement)
    return active, unresolved


def proof_present(requirement, atoms, coverage, texts):
    if requirement.get('contextual'):
        return True
    return any(all(span_present(atoms[aid], coverage, texts) for aid in alternative)
               for alternative in requirement['proofs'])


def evidence_status(requirement, atoms, coverage, texts):
    if proof_present(requirement, atoms, coverage, texts):
        return 'minimum-sufficient'
    overlap = any(
        texts[atoms[aid]['source_id']][max(a, atoms[aid]['start']):min(z, atoms[aid]['end'])].strip()
        for alternative in requirement['proofs'] for aid in alternative
        for a, z in coverage.get(atoms[aid]['source_id'], [])
        if max(a, atoms[aid]['start']) < min(z, atoms[aid]['end'])
    )
    return 'partial' if overlap else 'missing'


def score_evidence(family, atoms, coverage, texts):
    """Answer-independent complete methods, with explicit scenario assumptions.

    This returns coverage of calibrated requirements, not a numerically
    interchangeable replacement for the original bundled-fact metric.
    """
    validate_family(family, atoms)
    candidates = []
    for method in family['methods']:
        conditions = dict(family['conditions'], **method.get('conditions', {}))
        active, unresolved = active_requirements(family, method, conditions)
        status = {r['id']: evidence_status(r, atoms, coverage, texts) for r in active}
        hits = [rid for rid, value in status.items() if value == 'minimum-sufficient']
        candidates.append(dict(method=method['id'], assumptions=method.get('conditions', {}),
                               status=status, facts_hit=hits, unresolved=unresolved,
                               recall=len(hits) / len(active) if active else None,
                               complete=bool(active) and len(hits) == len(active) and not unresolved))
    chosen = max(candidates, key=lambda c: (c['complete'], c['recall'] or 0, len(c['facts_hit'])))
    if not family['positive_recall_applicable']:
        return dict(positive_recall=None, complete=None, methods=candidates,
                    clarification_support=chosen)
    return dict(positive_recall=chosen['recall'], complete=chosen['complete'],
                chosen_method=chosen['method'], methods=candidates)


def score_answer(family, atoms, texts, coverage, answer, review):
    """Validate exhaustive quote-bound manual semantic review, never guess it.

    annotations: start/end/type ('claim' or 'nontechnical'), verdict
    ('correct', 'incorrect', 'unresolved'), requirement_id or None, reviewed
    canonical fields, and explicit applicability triggers. All substantive
    claims, including optional additions, affect correctness and grounding.
    """
    validate_family(family, atoms)
    if (not review.get('reviewer_id') or review.get('origin') not in {'human', 'agent'}
            or review.get('method') != 'manual-semantic'
            or review.get('answer_sha256') != hashlib.sha256(answer.encode()).hexdigest()
            or review.get('all_substantive_claims_reviewed') is not True
            or review.get('conditions_reviewed') is not True):
        raise ValueError('Exhaustive, bound semantic review and provenance required')
    methods = {m['id']: m for m in family['methods']}
    if review['method_id'] not in methods:
        raise ValueError('Unknown chosen method')
    conditions = dict(family['conditions'])
    if not set(review.get('conditions', {})) <= set(conditions):
        raise ValueError('Unknown answer condition')
    # Question-fixed facts cannot be changed by answer annotations.
    for key, value in review.get('conditions', {}).items():
        if conditions[key] is not None and value != conditions[key]:
            raise ValueError('Answer review changes a question-fixed condition')
        conditions[key] = value
    requirements = {r['id']: r for r in family['requirements']}
    reviewed_ranges, claims = [], []
    for annotation in review['annotations']:
        start, end = annotation['start'], annotation['end']
        if not 0 <= start < end <= len(answer) or answer[start:end] != annotation['quote']:
            raise ValueError('Unbound answer annotation')
        if any(max(start, a) < min(end, z) for a, z in reviewed_ranges):
            raise ValueError('Overlapping answer annotations')
        reviewed_ranges.append((start, end))
        if annotation['type'] == 'nontechnical':
            continue
        if annotation['type'] != 'claim' or annotation['verdict'] not in {'correct', 'incorrect', 'unresolved'}:
            raise ValueError('Unknown semantic annotation')
        for key in annotation.get('triggers', []):
            if key not in conditions:
                raise ValueError('Unknown procedure trigger')
            if family['conditions'][key] is False:
                raise ValueError('Claim conflicts with a question-fixed scenario')
            conditions[key] = True
        rid = annotation.get('requirement_id')
        requirement = requirements.get(rid)
        fields = annotation.get('fields', {})
        errors = []
        if annotation['verdict'] == 'incorrect':
            errors.append('reviewed-technical-error')
        expected = requirement.get('invariants', {}) if requirement else {}
        missing = [key for key in expected if key not in fields]
        for key, value in expected.items():
            if key in fields:
                try:
                    equivalent = canonical(fields[key]) == canonical(value)
                except (ValueError, TypeError, ArithmeticError):
                    equivalent = False
                if not equivalent:
                    errors.append('incorrect-invariant:' + key)
        accepted = bool(requirement) and annotation['verdict'] == 'correct' and not errors and not missing
        # Reviewer must explicitly associate the claim with a registered proof;
        # source presence alone does not imply that an arbitrary sentence is grounded.
        cited = set(annotation.get('evidence', []))
        admissible = bool(requirement) and any(set(p) <= cited for p in requirement['proofs'])
        if cited - set(atoms):
            raise ValueError('Unknown cited evidence atom')
        grounded = accepted and admissible and any(
            set(p) <= cited and all(span_present(atoms[aid], coverage, texts) for aid in p)
            for p in requirement['proofs'])
        if requirement and requirement.get('contextual'):
            grounded = accepted and annotation.get('epistemic_only') is True
        claims.append(dict(requirement_id=rid, accepted=accepted, grounded=grounded,
                           errors=errors, missing_invariants=missing,
                           unresolved=annotation['verdict'] == 'unresolved' or bool(missing) or not requirement))
    covered = union(reviewed_ranges)
    cursor = 0
    for start, end in covered:
        if answer[cursor:start].strip():
            raise ValueError('Unreviewed answer text; possible unjustified claims')
        cursor = end
    if answer[cursor:].strip() or not claims:
        raise ValueError('Unreviewed answer or no substantive judgment')
    for key, expected in methods[review['method_id']].get('conditions', {}).items():
        if conditions.get(key) is not None and conditions[key] != expected:
            raise ValueError('Chosen method contradicts reviewed applicability')
    active, unresolved = active_requirements(family, methods[review['method_id']], conditions)
    accepted_ids = {c['requirement_id'] for c in claims if c['accepted']}
    grounded_ids = {c['requirement_id'] for c in claims if c['grounded']}
    missing = [r['id'] for r in active if r['id'] not in accepted_ids]
    critical_missing = [r['id'] for r in active if r['safety_critical'] and r['id'] not in accepted_ids]
    incorrect = any(c['errors'] for c in claims)
    uncertain = any(c['unresolved'] for c in claims) or bool(unresolved)
    correct = not incorrect and not uncertain
    complete = not missing and not unresolved
    grounded = all(c['grounded'] for c in claims)
    return dict(correctness='incorrect' if incorrect else ('unresolved' if uncertain else 'correct'),
                minimum_complete=complete, missing_required=missing,
                applicable_requirements=[r['id'] for r in active], conditions=conditions,
                unresolved_conditions=unresolved, critical_missing=critical_missing,
                safety_pass=not critical_missing and not incorrect and not unresolved,
                grounding='supported' if grounded else 'not-fully-supported',
                grounded_required=[r['id'] for r in active if r['id'] in grounded_ids],
                minimum_answer_pass=correct and complete and not critical_missing,
                grounded_answer_pass=correct and complete and not critical_missing and grounded,
                claims=claims, reviewer_origin=review['origin'], independent_validation=False)
