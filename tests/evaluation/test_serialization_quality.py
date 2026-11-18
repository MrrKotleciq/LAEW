"""S0/S1 paired payload and at-most-once runner acceptance; HTTP is intercepted."""
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import socket
import time

import pytest
import requests

from laew.cloud_chat import CloudError
from laew.eval.real_world_answer_plan import serialize
from laew.eval.serialization_quality_runner import Ledger, GuardedTransport, execute, validate_authorization
from laew.eval import serialization_quality_study as study
from laew.llm.cancellation import Cancellation


@pytest.fixture(autouse=True)
def network_forbidden(monkeypatch):
    def denied(*args,**kwargs):
        raise AssertionError('Real network forbidden in serialization quality tests')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)
    monkeypatch.setattr(requests.Session,'request',denied)


@pytest.fixture
def rows():
    result=[]
    for i in range(12):
        for arm in ('B','C'):
            for variant in ('S0','S1'):
                question='Synthetic original question '+str(i)
                context='Synthetic context '+arm+' '+variant
                payload=serialize(question,context)
                result.append(dict(sequence=len(result)+1,question_id=f'Q{i:02d}-en',arm=arm,
                    variant=variant,context=context,context_sha256=hashlib.sha256(context.encode()).hexdigest(),
                    payload=payload,payload_sha256=study.fmt.digest(study.fmt.canonical(payload))))
    return result


class Response:
    def __init__(self,frames,status=200,delay=0):
        self.frames,self.status_code,self.delay=frames,status,delay
        self.headers={'x-request-id':'synthetic-request'}

    def iter_content(self,chunk_size):
        for frame in self.frames:
            if self.delay:
                time.sleep(self.delay)
            yield ('data: '+json.dumps(frame)+'\n\n').encode()

    def close(self):
        pass


def frames():
    return [dict(type='response.output_text.delta',delta='Supported synthetic answer.'),
        dict(type='response.completed',response=dict(id='resp_synthetic',status='completed',
            model='gpt-5.6-luna',output=[],usage=dict(input_tokens=100,output_tokens=10,total_tokens=110,
                input_tokens_details={'cached_tokens':0},output_tokens_details={'reasoning_tokens':2})))]


def intercept(monkeypatch,ledger,response):
    calls=[]
    path=ledger.db.execute('PRAGMA database_list').fetchone()[2]
    def request(session,method,url,**kwargs):
        other=Ledger(path,ledger.rows)
        assert other.records()[-1]['status']=='reserved'
        other.close()
        assert method=='POST' and url=='https://api.openai.com/v1/responses'
        assert kwargs['allow_redirects'] is False
        assert all(a.max_retries.total==0 and a.max_retries.read==0 for a in session.adapters.values())
        calls.append(kwargs['json'])
        if isinstance(response,BaseException):
            raise response
        return response
    monkeypatch.setattr(requests.Session,'request',request)
    return calls


def test_48_attempts_and_49th_blocked_durably(tmp_path,rows,monkeypatch):
    ledger=Ledger(tmp_path/'attempts.db',rows)
    calls=intercept(monkeypatch,ledger,Response(frames()))
    for row in rows:
        assert execute(ledger,row,lambda:'synthetic-oauth','registration',authorized=True)
    assert len(calls)==48
    assert [r['payload'] for r in ledger.records()]==calls
    assert all(r['usage']['reasoning_tokens']==2 and r['server_model']=='gpt-5.6-luna'
               and r['latency_ms']>=0 for r in ledger.records())
    ledger.close()
    ledger=Ledger(tmp_path/'attempts.db',rows)
    with pytest.raises(CloudError,match='ATTEMPT_CAP'):
        ledger.reserve(rows[0])
    assert len(ledger.records())==48
    ledger.close()


def test_default_authorization_blocks_before_credentials(tmp_path,rows):
    ledger=Ledger(tmp_path/'attempts.db',rows)
    with pytest.raises(CloudError,match='SEPARATE_AUTHORIZATION_REQUIRED'):
        execute(ledger,rows[0],lambda:pytest.fail('Credential accessed'),'registration')
    assert not ledger.records()
    ledger.close()


@pytest.mark.parametrize('failure',['wrong_model','missing_model','snapshot_alias','missing_usage','invalid_usage',
    'bool_usage','cached_overflow','reasoning_overflow','input_cap','output_cap','missing_response_id',
    'stream_end','auth','rate_limit','http500','timeout_before','timeout_after','refusal','tool','stream_error'])
def test_errors_stop_without_retry(tmp_path,rows,monkeypatch,failure):
    fs=frames();terminal=fs[-1]['response'];usage=terminal['usage'];response=Response(fs)
    if failure=='wrong_model':terminal['model']='gpt-6-luna'
    elif failure=='snapshot_alias':terminal['model']='gpt-5.6-luna-2026-11-01'
    elif failure=='missing_model':del terminal['model']
    elif failure=='missing_usage':del terminal['usage']
    elif failure=='invalid_usage':usage['total_tokens']=111
    elif failure=='bool_usage':usage['input_tokens']=True
    elif failure=='cached_overflow':usage['input_tokens_details']['cached_tokens']=101
    elif failure=='reasoning_overflow':usage['output_tokens_details']['reasoning_tokens']=11
    elif failure=='input_cap':usage.update(input_tokens=12001,total_tokens=12011)
    elif failure=='output_cap':usage.update(output_tokens=4097,total_tokens=4197)
    elif failure=='missing_response_id':del terminal['id']
    elif failure=='stream_end':fs.pop()
    elif failure in ('auth','rate_limit','http500'):response.status_code={'auth':401,'rate_limit':429,'http500':500}[failure]
    elif failure=='timeout_before':response=requests.Timeout()
    elif failure=='timeout_after':response=Response(fs,delay=.03)
    elif failure=='refusal':fs[0]['type']='response.refusal.delta'
    elif failure=='tool':terminal['output']=[{'type':'function_call'}]
    elif failure=='stream_error':fs[-1]={'type':'response.failed','response':{'error':{'code':'usage_limit_reached'}}}
    ledger=Ledger(tmp_path/'attempts.db',rows)
    calls=intercept(monkeypatch,ledger,response)
    assert not execute(ledger,rows[0],lambda:'synthetic-oauth','registration',authorized=True,
                       watchdog=.01 if failure=='timeout_after' else 5)
    assert len(calls)==1 and len(ledger.records())==1
    assert ledger.records()[0]['status']=='failed' and ledger.meta('stop')
    ledger.close()
    ledger=Ledger(tmp_path/'attempts.db',rows)
    with pytest.raises(CloudError,match='EXPERIMENT_STOPPED'):
        ledger.reserve(rows[1])
    ledger.close()


@pytest.mark.parametrize('tamper',['context','question','instructions','variant','arm','sequence','rebound_context'])
def test_tamper_blocked_before_http(tmp_path,rows,monkeypatch,tamper):
    ledger=Ledger(tmp_path/'attempts.db',rows)
    calls=intercept(monkeypatch,ledger,Response(frames()))
    row=copy.deepcopy(rows[0])
    if tamper=='context':row['context']+='new text'
    elif tamper=='question':row['payload']['input'][0]['content']+='gold'
    elif tamper=='instructions':row['payload']['instructions']+='gold'
    elif tamper=='variant':row['variant']='S1'
    elif tamper=='arm':row['arm']='C'
    elif tamper=='sequence':row['sequence']=2
    else:
        row['context']='new body';row['context_sha256']=hashlib.sha256(row['context'].encode()).hexdigest()
        row['payload']=serialize('new question',row['context'])
    assert not execute(ledger,row,lambda:'synthetic-oauth','registration',authorized=True)
    assert not calls and not ledger.records()
    ledger.close()


@pytest.mark.parametrize('crash',['before_http','after_http_uncertain','after_complete_before_save'])
def test_restart_never_reuses_uncertain_reservation(tmp_path,rows,crash):
    path=tmp_path/'attempts.db';ledger=Ledger(path,rows)
    record=ledger.reserve(rows[0])
    if crash!='before_http':
        record['answer']='Partial or completed server output';ledger.save(record)
    ledger.close()
    ledger=Ledger(path,rows)
    for row in rows[:2]:
        with pytest.raises(CloudError,match='UNCERTAIN_DISPATCH'):ledger.reserve(row)
    assert len(ledger.records())==1
    ledger.close()


def test_two_connections_global_reservation_and_changed_schedule(tmp_path,rows):
    path=tmp_path/'attempts.db';one=Ledger(path,rows);two=Ledger(path,rows)
    one.reserve(rows[0])
    with pytest.raises(CloudError,match='UNCERTAIN_DISPATCH'):two.reserve(rows[1])
    one.close();two.close()
    changed=copy.deepcopy(rows);changed[0]['payload']['instructions']+='changed'
    with pytest.raises(CloudError,match='FIXTURE_CHANGED'):Ledger(path,changed)


def test_restart_after_completion_resumes_next_only(tmp_path,rows,monkeypatch):
    path=tmp_path/'attempts.db';ledger=Ledger(path,rows)
    calls=intercept(monkeypatch,ledger,Response(frames()))
    assert execute(ledger,rows[0],lambda:'synthetic-oauth','registration',authorized=True)
    ledger.close();ledger=Ledger(path,rows)
    assert execute(ledger,rows[1],lambda:'synthetic-oauth','registration',authorized=True)
    assert len(calls)==2 and [r['sequence'] for r in ledger.records()]==[1,2]
    ledger.close()


def test_registration_and_wall_ceiling(tmp_path,rows,monkeypatch):
    ledger=Ledger(tmp_path/'attempts.db',rows)
    calls=intercept(monkeypatch,ledger,Response(frames()))
    assert execute(ledger,rows[0],lambda:'synthetic-oauth','registration',authorized=True)
    assert not execute(ledger,rows[1],lambda:'synthetic-oauth','different',authorized=True)
    assert len(calls)==1 and len(ledger.records())==1
    ledger.close()
    other=Ledger(tmp_path/'old.db',rows)
    other.db.execute('INSERT INTO meta VALUES (?,?)',('started_epoch',str(time.time()-5401)));other.db.commit()
    with pytest.raises(CloudError,match='WALL_CEILING'):other.reserve(rows[0])
    other.close()


def test_forced_continuation_cannot_dispatch_twice(tmp_path,rows,monkeypatch):
    from laew.agent import AgentExecutor
    from laew.llm.base import LLMMessage,MessageRole
    original=AgentExecutor.run
    def force(executor,*args,**kwargs):
        original(executor,*args,**kwargs)
        executor.agent.provider.generate_tools([LLMMessage(MessageRole.USER,'forced final')],'gpt-5.6-luna',[])
    monkeypatch.setattr(AgentExecutor,'run',force)
    ledger=Ledger(tmp_path/'attempts.db',rows);calls=intercept(monkeypatch,ledger,Response(frames()))
    assert not execute(ledger,rows[0],lambda:'synthetic-oauth','registration',authorized=True)
    assert len(calls)==1 and len(ledger.records())==1 and ledger.meta('stop')
    ledger.close()


@pytest.mark.parametrize('provider,model',[('openai-api','gpt-5.6-luna'),('chatgpt','gpt-6-luna')])
def test_provider_model_guard_before_http(tmp_path,rows,provider,model):
    ledger=Ledger(tmp_path/'attempts.db',rows);transport=GuardedTransport(ledger,rows[0],'registration')
    with pytest.raises(CloudError,match='PROVIDER_MODEL'):
        list(transport.stream('synthetic-oauth',provider,model,rows[0]['payload']['input'],Cancellation(),
            tools=[],instructions=rows[0]['payload']['instructions']))
    assert not ledger.records();ledger.close()


@pytest.mark.parametrize('field',['explicit_new_user_authorization','attempts','provider','model',
    'generator_manifest_sha256','plan_percentage_not_predictable_accepted','source_owner_review'])
def test_authorization_is_separate_and_scoped(rows,field):
    pairs=sorted({(r['question_id'],r['arm']) for r in rows})
    authorization=dict(explicit_new_user_authorization=True,attempts=48,provider='chatgpt',model='gpt-5.6-luna',
        generator_manifest_sha256='manifest',plan_percentage_not_predictable_accepted=True,
        source_owner_review=dict(reviewer_id='owner',visible_attribution_adequate=True,
            reviewed_question_arm_pairs=[list(p) for p in pairs],critical_unresolved_attribution_issues=[]))
    validate_authorization(authorization,rows,'manifest')
    del authorization[field]
    with pytest.raises(CloudError):validate_authorization(authorization,rows,'manifest')


@pytest.fixture(scope='module')
def frozen():
    root=os.environ.get('LAEW_SERIALIZATION_QUALITY_ROOT')
    if not root:pytest.skip('External S0/S1 package not configured')
    return Path(root)


def test_frozen_pairs_original_payloads_and_order(frozen):
    result=study.verify(frozen)
    assert result['requests']==48 and all(x['unchanged'] for x in result['protected'])
    rows=study.read(frozen/'generator-only/requests.json')
    assert len({(r['question_id'],r['arm'],r['variant']) for r in rows})==48
    assert all(len(r['payload']['input'])==1 and r['payload']['tools']==[] and
               'previous_response_id' not in r['payload'] for r in rows)


def test_all_120_contexts_risks_and_exact_body_counts(frozen):
    audits=study.read(frozen/'provenance-audit.json')
    assert len(audits)==120 and len({a['question_id'] for a in audits})==60
    assert sum(len(a['passages']) for a in audits)==441
    assert sum(a['body_characters'] for a in audits)==313599
    assert all(a['exact_body_preserved'] and a['outer_attribution_preserved'] for a in audits)
    assert all('R02' not in a['risks'] and 'R01' in a['risks'] for a in audits)
    register=study.read(frozen/'provenance-risk-register.json')
    for risk in register:
        assert risk['question_ids']==sorted({a['question_id'] for a in audits if risk['id'] in a['risks']})


def test_subset_deterministic_language_balanced_and_no_outcome_inputs(frozen):
    config=study.read(study.PARENT/'inputs/study-config.json')
    qs=study.read(Path(config['questions'])/'questions-only.json')
    selected=study.select_questions(list(reversed(qs)))
    assert selected==study.read(frozen/'generator-only/questions-only.json')
    assert study.Counter(q['language'] for q in selected)=={'de':4,'en':4,'pl':4}
    altered=copy.deepcopy(qs);altered[0]['gold']='leak'
    with pytest.raises(ValueError):study.select_questions(altered)


def test_no_gold_review_material_in_generator_inputs(frozen):
    gen=frozen/'generator-only'
    assert {p.name for p in gen.iterdir()}=={'questions-only.json','requests.json','settings.json','integrity.json'}
    rows=study.read(gen/'requests.json')
    config=study.read(study.PARENT/'inputs/study-config.json')
    qs={q['id']:q for q in study.read(Path(config['questions'])/'questions-only.json')}
    for r in rows:
        assert r['payload']==serialize(qs[r['question_id']]['text'],r['context'])
    form=(frozen/'review-only/manual-review.html').read_text(encoding='utf-8')
    assert 'Answer S0' not in form and 'Answer S1' not in form and 'curator-key' not in form
    assert '"variant"' not in form and '"request_sequence"' not in form
    assert '<option value="">Unreviewed</option>' in form
    data=study.read(frozen/'review-only/blank-review.json')
    assert all(a['answer'] is None and all(v is None for v in a['dimensions'].values())
               for c in data['cases'] for a in c['answers'])


@pytest.mark.parametrize('tamper',['body','order','range','source','heading'])
def test_frozen_contract_tamper_is_rejected(frozen,tamper):
    record,frame=next((r,f) for r,f in study.load_frames(study.PARENT/'inputs') if r['kind']=='primary-selected')
    saved={r['variant']:r for r in study.read(study.PARENT/'delivery/serialized-contexts.json')
        if r['question_id']==record['question_id'] and r['arm']==record['arm'] and r['kind']=='primary-selected'}
    p=frame.passages[0]
    if tamper=='body':p=replace(p,body=p.body+'extra')
    elif tamper=='range':p=replace(p,ranges=((0,1),))
    elif tamper=='source':p=replace(p,source_key='unknown')
    elif tamper=='heading':p=replace(p,metadata_json=study.fmt.canonical({'section_header':'gold'}))
    changed=replace(frame,passages=(p,*frame.passages[1:]))
    if tamper=='order':changed=replace(frame,passages=tuple(reversed(frame.passages)))
    with pytest.raises(ValueError):study.verify_pair(record,changed,saved)


def test_generator_manifest_tamper(tmp_path):
    (tmp_path/'payload.json').write_text('{}')
    pin=study.seal(tmp_path)
    (tmp_path/'payload.json').write_text('{"new":"gold"}')
    with pytest.raises(ValueError):study.verify_manifest(tmp_path,'integrity.json',pin)


def test_review_does_not_score_unreviewed_claims_or_guess_conditions(frozen):
    family=study.read(frozen/'review-only/rubric-v2.1.json')['families']['P04']
    review=dict(condition_decisions={})
    if any(v is None for v in family['conditions'].values()):
        with pytest.raises(ValueError,match='scoped decisions'):
            study.reviewed_answer_score(frozen,'P04-de','B','A plausible unreviewed answer.',review)
    review['condition_decisions']={k:dict(kind='unknown',reason='Unreviewed',quotes=[])
        for k,v in family['conditions'].items() if v is None}
    with pytest.raises(ValueError,match='Exhaustive'):
        study.reviewed_answer_score(frozen,'P04-de','B','A plausible unreviewed answer.',review)


def test_bind_retains_failed_uncertain_and_unattempted_answers(frozen,tmp_path):
    rows=study.read(frozen/'generator-only/requests.json')
    ledger=Ledger(tmp_path/'answers.db',rows)
    record=ledger.reserve(rows[0]);record.update(answer='Partial answer.',status='failed',
        answer_sha256=study.fmt.digest('Partial answer.'));ledger.save(record);ledger.close()
    destination=tmp_path/'review'
    study.bind_answers(frozen,tmp_path/'answers.db',destination)
    data=study.read(destination/'blank-review.json')
    answers=[a for c in data['cases'] for a in c['answers']]
    assert sum(a['attempt_status']=='failed' for a in answers)==1
    assert sum(a['attempt_status']=='not-attempted' for a in answers)==47
    assert any(a['answer']=='Partial answer.' for a in answers)
    assert all(v is None for a in answers for v in a['dimensions'].values())


def test_bind_rejects_changed_answer_hash(frozen,tmp_path):
    rows=study.read(frozen/'generator-only/requests.json')
    ledger=Ledger(tmp_path/'answers.db',rows)
    record=ledger.reserve(rows[0]);record.update(answer='Changed answer.',status='failed',
        answer_sha256=study.fmt.digest('Original answer.'));ledger.save(record);ledger.close()
    with pytest.raises(ValueError,match='text/hash'):
        study.bind_answers(frozen,tmp_path/'answers.db',tmp_path/'review')
