"""Fictional, quote-bound condition categories; no benchmark facts or services."""
import copy
import hashlib

import pytest

from laew.eval.scoring_calibration import answer_conditions, score_answer, score_evidence


def fixture(answer='Use route A. If dirty, wash. Keep dry.'):
    text='Route A is valid. Washing requires dryness.'
    atoms={'route':dict(source_id='manual',start=0,end=17),
           'dry':dict(source_id='manual',start=18,end=len(text))}
    family=dict(conditions={'washing':None},positive_recall_applicable=True,
        requirements=[dict(id='route',category='essential',proofs=[['route']],
                           invariants={'version':'2'},safety_critical=False,rationale='Valid route.'),
                      dict(id='dry',category='conditional',when={'washing':True},proofs=[['dry']],
                           safety_critical=True,rationale='Required if advising washing.')],
        methods=[dict(id='A',required=['route'],conditions={'washing':False})])
    def claim(start,end,rid,**extra):
        return dict(start=start,end=end,quote=answer[start:end],type='claim',verdict='correct',
                    requirement_id=rid,fields={'version':'2'} if rid=='route' else {},
                    evidence=[rid],**extra)
    review=dict(reviewer_id='synthetic-reviewer',origin='agent',method='manual-semantic',
        method_id='A',answer_sha256=hashlib.sha256(answer.encode()).hexdigest(),
        all_substantive_claims_reviewed=True,conditions_reviewed=True,
        conditions={'washing':True},annotations=[claim(0,len(answer),'route')])
    return family,atoms,{'manual':text},{'manual':[(0,len(text))]},review


def decision(answer,kind,needle=None):
    quotes=[]
    if needle:
        start=answer.index(needle);quotes=[dict(start=start,end=start+len(needle),quote=needle)]
    return dict(washing=dict(kind=kind,reason='Explicit synthetic semantic judgment.',quotes=quotes))


def test_fixed_question_fact_cannot_be_overridden_by_review_or_trigger():
    answer='Use route A and wash.'
    f,a,t,c,r=fixture(answer);f['conditions']['washing']=False
    with pytest.raises(ValueError,match='question-fixed'):
        score_answer(f,a,t,c,answer,r)
    r['conditions']['washing']=False;r['annotations'][0]['triggers']=['washing']
    with pytest.raises(ValueError,match='question-fixed'):
        score_answer(f,a,t,c,answer,r)


@pytest.mark.parametrize('kind',['recommended','conditional_recommendation','explanation'])
def test_advice_or_relevant_explanation_activates_warning_despite_false_method_assumption(kind):
    answer='Use route A. If dirty, wash.'
    f,a,t,c,r=fixture(answer)
    r['condition_decisions']=decision(answer,kind,'wash')
    result=score_answer(f,a,t,c,answer,r)
    assert result['correctness']=='correct'
    assert result['critical_missing']==['dry'] and not result['minimum_answer_pass']
    assert result['condition_trace']['washing']['kind']==kind
    assert not result['condition_review_gaps']


def test_conditional_procedure_with_its_warning_can_pass():
    answer='Route A. If dirty wash; keep dry.'
    f,a,t,c,r=fixture(answer);split=answer.index(' If')
    r['annotations'][0].update(end=split,quote=answer[:split])
    r['annotations'].append(dict(start=split,end=len(answer),quote=answer[split:],type='claim',
        verdict='correct',requirement_id='dry',fields={},evidence=['dry']))
    r['condition_decisions']=decision(answer,'conditional_recommendation','If dirty wash')
    assert score_answer(f,a,t,c,answer,r)['grounded_answer_pass']


def test_pure_hypothetical_mention_does_not_activate_a_procedure():
    answer='Use route A. Washing is only a hypothetical topic, not recommended here.'
    f,a,t,c,r=fixture(answer);r['conditions']['washing']=False
    r['condition_decisions']=decision(answer,'hypothetical_mention','not recommended here')
    result=score_answer(f,a,t,c,answer,r)
    assert result['minimum_answer_pass'] and result['applicable_requirements']==['route']
    r['annotations'][0]['triggers']=['washing']
    with pytest.raises(ValueError,match='contradicts scoped'):
        score_answer(f,a,t,c,answer,r)


@pytest.mark.parametrize('method_value',[False,True])
def test_unknown_is_not_resolved_by_a_method_scenario(method_value):
    answer='Use route A; washing applicability is unknown.'
    f,a,t,c,r=fixture(answer);f['methods'][0]['conditions']['washing']=method_value
    r['conditions']['washing']=None;r['condition_decisions']=decision(answer,'unknown')
    result=score_answer(f,a,t,c,answer,r)
    assert result['correctness']=='unresolved' and not result['minimum_complete']
    assert result['unresolved_conditions']==['dry'] and not result['safety_pass']


def test_wrong_version_remains_a_technical_error_after_applicability_repair():
    answer='Use route A for version 1.'
    f,a,t,c,r=fixture(answer);r['conditions']['washing']=False
    r['annotations'][0]['fields']['version']='1'
    result=score_answer(f,a,t,c,answer,r)
    assert result['correctness']=='incorrect' and not result['minimum_answer_pass']


def test_missing_scope_provenance_is_reported_without_guessing():
    answer='Use route A.'
    f,a,t,c,r=fixture(answer);r['conditions']['washing']=False
    result=score_answer(f,a,t,c,answer,r)
    assert result['condition_review_gaps']==['washing']
    assert result['condition_trace']['washing']['kind']=='legacy_reviewed'


@pytest.mark.parametrize('failure',['missing','quote','value','kind'])
def test_bad_scoped_annotations_fail_closed(failure):
    answer='Use route A; wash.'
    f,a,t,c,r=fixture(answer);r['condition_decisions']=decision(answer,'recommended','wash')
    if failure=='missing':r['condition_decisions']={}
    elif failure=='quote':r['condition_decisions']['washing']['quotes'][0]['quote']='invented'
    elif failure=='value':r['conditions']['washing']=False
    else:r['condition_decisions']['washing']['kind']='guessed-from-keywords'
    with pytest.raises(ValueError):score_answer(f,a,t,c,answer,r)


def test_question_fixed_provenance_and_evidence_scoring_are_unchanged():
    answer='Use route A.'
    f,a,t,c,r=fixture(answer);r['conditions']['washing']=False
    before=copy.deepcopy((f,a,t,c,r));score=score_evidence(f,a,c,t)
    assert score['methods'][0]['assumptions']=={'washing':False}
    assert score['complete']
    f['conditions']['washing']=False
    values,trace,gaps=answer_conditions(f,answer,r)
    assert values=={'washing':False} and trace['washing']['kind']=='question_fixed' and gaps==[]
    f['conditions']['washing']=None
    assert (f,a,t,c,r)==before
