"""Manually authored semantic-review fixtures; no model-generated answers."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from laew.eval.scoring_calibration import score_answer, score_evidence, validate_atoms


def fixture():
    # Fictional device avoids embedding benchmark reference answers in tests.
    texts = {'manual-v2': 'Use method A or method B. Keep dry. Rated 5 V. Only version 2.'}
    def atom(aid, value):
        start = texts['manual-v2'].index(value)
        return dict(id=aid, source_id='manual-v2', revision='2', start=start,
                    end=start + len(value), text=value,
                    text_sha256=hashlib.sha256(value.encode()).hexdigest(),
                    normalized_sha256=hashlib.sha256(texts['manual-v2'].encode()).hexdigest(),
                    rationale='Manually selected complete fictional source proposition.',
                    original_location={'page': 1})
    atoms = {key: atom(key, value) for key, value in {
        'a': 'Use method A', 'b': 'method B', 'dry': 'Keep dry.',
        'power': 'Rated 5 V.', 'version': 'Only version 2.'}.items()}
    def requirement(rid, category, proofs, **kwargs):
        return dict(id=rid, category=category, proofs=proofs, safety_critical=False,
                    rationale='Synthetic manual requirement.', **kwargs)
    requirements = [requirement('method-a', 'alternative', [['a']]),
                    requirement('method-b', 'alternative', [['b']]),
                    requirement('power', 'essential', [['power']],
                                invariants={'voltage': {'value': 5, 'unit': 'V'},
                                            'version': '2', 'dry_required': True}),
                    requirement('details', 'optional', [['version']]),
                    requirement('dry', 'conditional', [['dry']], when={'cleaning_advised': True})]
    requirements[-1]['safety_critical'] = True
    family = dict(conditions={'cleaning_advised': None}, requirements=requirements,
                  positive_recall_applicable=True,
                  methods=[dict(id='A', required=['method-a','power']),
                           dict(id='B', required=['method-b','power'])])
    return texts, atoms, family


def review_answer(answer, method='A', cleaning=False, *, atom='a', fields=None):
    # Reviewed semantics are independent of surface wording; annotator binds
    # each sentence to a requirement and preserves checked canonical meanings.
    fields = fields or {'voltage': {'value': 5, 'unit': 'V'}, 'version': '2', 'dry_required': True}
    chunks = answer.split('|')
    annotations, cursor = [], 0
    for index, text in enumerate(chunks):
        start = cursor
        end = start + len(text)
        rid = ('method-a' if method == 'A' else 'method-b') if index == 0 else 'power'
        annotations.append(dict(start=start, end=end, quote=text, type='claim', verdict='correct',
                                requirement_id=rid, fields={} if index == 0 else fields,
                                evidence=[atom] if index == 0 else ['power']))
        cursor = end
        if index + 1 < len(chunks):
            annotations.append(dict(start=cursor, end=cursor+1, quote='|', type='nontechnical'))
            cursor += 1
    return dict(reviewer_id='fixture-reviewer', origin='human', method='manual-semantic',
                method_id=method, answer_sha256=hashlib.sha256(answer.encode()).hexdigest(),
                all_substantive_claims_reviewed=True, conditions_reviewed=True,
                conditions={'cleaning_advised': cleaning}, annotations=annotations)


@pytest.mark.parametrize('answer', ['Choose A.|Use 5 V for v2; keep dry.',
                                   'The A route suffices.|The second edition specifies five volts, and dryness remains required.'])
def test_short_correct_and_equivalent_wording_pass_with_semantic_review(answer):
    texts, atoms, family = fixture()
    result = score_answer(family, atoms, texts, {'manual-v2': [(0,len(texts['manual-v2']))]},
                          answer, review_answer(answer))
    assert result['minimum_answer_pass'] and result['grounded_answer_pass']
    assert 'details' not in result['missing_required']


def test_one_independent_method_is_sufficient():
    texts, atoms, family = fixture()
    answer = 'Choose B.|5 V, version 2, keep dry.'
    result = score_answer(family, atoms, texts, {'manual-v2': [(0,100)]}, answer,
                          review_answer(answer, method='B', atom='b'))
    assert result['grounded_answer_pass']
    assert 'method-a' not in result['applicable_requirements']


@pytest.mark.parametrize('field,value', [('version','1'), ('dry_required',False),
                                       ('voltage',{'value':5,'unit':'A'}),
                                       ('voltage',{'value':5000,'unit':'V'})])
def test_longer_wrong_version_units_values_or_negation_fail(field,value):
    texts, atoms, family = fixture()
    if field == 'voltage':
        erroneous = ('For version 2, the required supply is 5 A; keep dry.'
                     if value['unit'] == 'A' else
                     'For version 2, use 5000 V and keep the device dry.')
    else:
        erroneous = {'version': 'For version 1, use 5 V and keep the device dry.',
                     'dry_required': 'For version 2, use 5 V; keeping the device dry is unnecessary.'}[field]
    answer = 'After a long discussion of the available routes, choose A.|' + erroneous
    review = review_answer(answer)
    review['annotations'][-1]['fields'][field] = value
    result = score_answer(family, atoms, texts, {'manual-v2': [(0,100)]}, answer, review)
    assert result['correctness'] == 'incorrect' and not result['minimum_answer_pass']


def test_equivalent_physical_units_pass():
    texts, atoms, family = fixture()
    answer = 'A.|0.005 kV, version 2, keep dry.'
    review = review_answer(answer)
    review['annotations'][-1]['fields']['voltage'] = {'value':'.005','unit':'kV'}
    assert score_answer(family, atoms, texts, {'manual-v2':[(0,100)]}, answer, review)['minimum_answer_pass']


def test_missing_applicable_critical_warning_fails_and_unknown_is_not_waived():
    texts, atoms, family = fixture()
    answer = 'Use A and clean it.|5 V, version 2.'
    review = review_answer(answer, cleaning=False)
    review['annotations'][0]['triggers'] = ['cleaning_advised']
    result = score_answer(family, atoms, texts, {'manual-v2':[(0,100)]}, answer, review)
    assert result['critical_missing'] == ['dry'] and not result['minimum_answer_pass']
    review = review_answer(answer, cleaning=None)
    result = score_answer(family, atoms, texts, {'manual-v2':[(0,100)]}, answer, review)
    assert result['unresolved_conditions'] == ['dry'] and not result['minimum_answer_pass']


def test_complete_conditional_warning_passes():
    texts,atoms,family=fixture()
    answer='A.|5 V, version 2.|Keep dry while cleaning.'
    review=review_answer(answer,cleaning=True)
    review['annotations'][-1].update(requirement_id='dry',fields={},evidence=['dry'])
    result=score_answer(family,atoms,texts,{'manual-v2':[(0,100)]},answer,review)
    assert result['grounded_answer_pass'] and not result['critical_missing']


def test_correct_but_missing_required_fact_is_incomplete_not_factually_incorrect():
    texts,atoms,family=fixture()
    answer='A.'
    review=review_answer(answer)
    result=score_answer(family,atoms,texts,{'manual-v2':[(0,100)]},answer,review)
    assert result['correctness']=='correct' and not result['minimum_complete']
    assert result['missing_required']==['power']


def test_correctness_and_grounding_remain_separate():
    texts, atoms, family = fixture()
    answer='A.|5 V, version 2, keep dry.'
    result=score_answer(family,atoms,texts,{},answer,review_answer(answer))
    assert result['correctness']=='correct' and result['minimum_complete']
    assert result['minimum_answer_pass'] and not result['grounded_answer_pass']


def test_unreviewed_extra_claim_is_detected():
    texts,atoms,family=fixture()
    answer='A.|5 V, version 2, keep dry.'
    review=review_answer(answer)
    extended=answer+' The device is also safe to operate underwater.'
    review['answer_sha256']=hashlib.sha256(extended.encode()).hexdigest()
    with pytest.raises(ValueError, match='Unreviewed answer'):
        score_answer(family,atoms,texts,{},extended,review)


def test_annotated_unsupported_conclusion_fails_even_if_verbose():
    texts,atoms,family=fixture()
    answer='A.|The device remains safe underwater at 100 V.'
    review=review_answer(answer)
    review['annotations'][-1].update(requirement_id=None,verdict='unresolved',evidence=[],fields={})
    result=score_answer(family,atoms,texts,{},answer,review)
    assert result['correctness']=='unresolved' and not result['minimum_answer_pass']


def test_optional_omission_is_allowed_but_incorrect_optional_addition_fails():
    texts,atoms,family=fixture()
    answer='A.|5 V, version 2, keep dry.|The manual only applies to version 1.'
    review=review_answer(answer)
    review['annotations'][-1].update(requirement_id='details',verdict='incorrect',fields={},evidence=['version'])
    result=score_answer(family,atoms,texts,{'manual-v2':[(0,100)]},answer,review)
    assert result['minimum_complete'] and result['correctness']=='incorrect'
    assert not result['minimum_answer_pass']


def test_proper_clarification_passes_without_invented_technical_answer():
    texts,atoms,family=fixture()
    family['requirements']=[dict(id='clarify',category='essential',proofs=[],safety_critical=True,
        contextual=True,invariants={'technical_conclusion':False},rationale='Unknown user version cannot be inferred.')]
    family['conditions']={};family['methods']=[dict(id='clarification',required=['clarify'])]
    family['positive_recall_applicable']=False
    answer='Which device version do you have? I cannot select the procedure without it.'
    review=review_answer(answer);review.update(method_id='clarification',conditions={})
    review['annotations']=[dict(start=0,end=len(answer),quote=answer,type='claim',verdict='correct',
        requirement_id='clarify',fields={'technical_conclusion':False},evidence=[],epistemic_only=True)]
    result=score_answer(family,atoms,texts,{},answer,review)
    assert result['grounded_answer_pass']
    evidence=score_evidence(family,atoms,{},texts)
    assert evidence['positive_recall'] is None and evidence['complete'] is None
    review['annotations'][0]['fields']['technical_conclusion']=True
    assert not score_answer(family,atoms,texts,{},answer,review)['minimum_answer_pass']


def test_minimum_evidence_partial_missing_and_version_integrity():
    texts,atoms,family=fixture()
    for method in family['methods']:
        method['conditions']={'cleaning_advised':False}
    result=score_evidence(family,atoms,{'manual-v2':[(0,3)]},texts)
    assert result['methods'][0]['status']['method-a']=='partial'
    assert result['methods'][0]['status']['power']=='missing'
    assert not result['complete']
    result=score_evidence(family,atoms,{'manual-v2':[(0,100)]},texts)
    assert result['complete']
    units={'manual-v2':{'revision':'2','normalized_sha256':atoms['a']['normalized_sha256']}}
    validate_atoms(atoms,texts,units)
    changed=copy.deepcopy(atoms);changed['a']['revision']='1'
    with pytest.raises(ValueError,match='version'):
        validate_atoms(changed,texts,units)


@pytest.fixture(scope='module')
def real_calibration():
    root=os.environ.get('LAEW_SCORING_CALIBRATION_ROOT')
    corpus=os.environ.get('LAEW_FROZEN_CORPUS_ROOT')
    retrieval=os.environ.get('LAEW_REAL_WORLD_RETRIEVAL')
    if not all((root,corpus,retrieval)):
        pytest.skip('Set calibration, frozen corpus and preserved retrieval paths')
    root,corpus,retrieval=Path(root),Path(corpus),Path(retrieval)
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    manifest=read(root/'rubric-manifest-v2.1.json')
    for entry in manifest['files']:
        assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
    units={u['id']:u for u in read(corpus/'corpus/source-manifest.json')['source_units']}
    texts={sid:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for sid,u in units.items()}
    return root,corpus,retrieval,read,units,texts


def test_all_real_facts_variants_and_source_proofs_are_covered(real_calibration):
    root,corpus,retrieval,read,units,texts=real_calibration
    rubric=read(root/'rubric-v2.1.json');atoms=read(root/'source-atoms-v2.1.json')
    assert len(rubric['families'])==20
    classification=read(root/'fact-classification-v2.1.json')
    original_facts={f['id'] for dirname in ['stage-2b2-real-world-pilot-20261113-v4','stage-2b2-real-world-sealed-20261113-v3']
                    for family in read(corpus.parent/dirname/'families.json') for f in family['facts']}
    assert {c['original_fact_id'] for c in classification}==original_facts
    assert len(original_facts)==46
    validate_atoms(atoms,texts,units)
    restrictions=read(corpus/'review/r3d/restricted-regions.json')['regions']
    for family in rubric['families'].values():
        assert set(family['questions'])=={'en','pl','de'} and family['minimum_sufficient_answer']
        assert all(not (r['category']=='optional' and r['safety_critical']) for r in family['requirements'])
    for atom in atoms.values():
        for region in restrictions:
            if region['source_id']==atom['source_id']:
                assert all(max(atom['start'],r['start'])>=min(atom['end'],r['end'])
                           for r in region['component_ranges']+region['related_context_ranges'])


def test_real_pilot_local_override_suffices_but_missing_preparation_does_not(real_calibration):
    from laew.eval.real_world_retrieval import coverage_of
    root,corpus,retrieval,read,units,texts=real_calibration
    rubric=read(root/'rubric-v2.1.json');atoms=read(root/'source-atoms-v2.1.json')
    traces=read(retrieval/'run-v2/retrieval-traces.json')
    for trace in traces:
        if trace['family_id'] not in {'P01','P02'}:
            continue
        result=score_evidence(rubric['families'][trace['family_id']],atoms,coverage_of(trace['selected']),texts)
        assert result['complete']==(trace['family_id']=='P01')
