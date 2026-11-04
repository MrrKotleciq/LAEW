"""The taxonomy is a backend contract, even when a provider ignores its enum."""
import json
from types import SimpleNamespace

import pytest

from laew.memory.categories import (
    CATEGORY_DESCRIPTIONS, CATEGORIES, ALIASES, InvalidMemoryCategory, normalize_category,
)
from laew.memory.service import MemoryService, EXTRACTION_PROMPT
from laew.memory.store import MemoryStore
from laew.memory.tool import MemoryTool
from laew.tools.schema import tool_definitions
from tests.unit.test_memory import conversation


@pytest.fixture
def memory(tmp_path):
    return MemoryService(MemoryStore(tmp_path/'memory.db'))


def test_tool_schema_and_local_description_share_backend_contract(memory):
    tool=MemoryTool(memory)
    definition=tool_definitions({tool.name:tool})[0]
    category=definition['parameters']['properties']['category']
    assert set(category['enum'])==CATEGORIES
    assert 'category' in definition['parameters']['required']
    for name,description in CATEGORY_DESCRIPTIONS.items():
        assert name in tool.description and description in tool.description
        assert name in EXTRACTION_PROMPT and description in EXTRACTION_PROMPT


@pytest.mark.parametrize('category',sorted(CATEGORIES))
def test_contract_supported_by_store_proposal_review_and_legacy_restart(memory,category):
    row=memory.store.remember('Legacy '+category,category=category)
    proposal=memory.create_proposal('New '+category,category=category)
    assert memory.decide(proposal,True)['memory_id']
    restarted=MemoryStore(memory.store.path)
    assert restarted.get(row['id'])['category']==category
    assert len(restarted.list_memories())==2
    assert restarted.update(row['id'],'Updated legacy '+category,1)['category']==category


@pytest.mark.parametrize('alias,expected',list(ALIASES.items())+[(' Goal ','goal'),('FACT','fact')])
def test_unambiguous_normalization_at_all_write_boundaries(memory,alias,expected):
    assert normalize_category(alias)==expected
    row=memory.store.remember('First fact',category=alias)
    assert row['category']==expected
    assert memory.store.update(row['id'],'Updated fact',1,alias)['category']==expected
    result=MemoryTool(memory).call('propose',content='Second fact',scope='user',category=alias)
    assert result.success and memory.proposals()[0]['category']==expected
    assert memory.decide(result.data['proposal_id'],True)['memory_id']
    assert all(row['category']==expected for row in memory.store.list_memories())


@pytest.mark.parametrize('category',['travel','travel_goal','personal','preferencje i plany podróżnicze','',None,[],{}])
def test_invalid_categories_have_actionable_error_and_no_write(memory,category):
    for invoke in (MemoryTool(memory).call,MemoryTool(memory).execute):
        result=invoke('propose',content='Visit Edinburgh',scope='user',category=category)
        assert not result.success and result.error_code=='ERR_INVALID_INPUT'
        assert result.data['retryable'] is True
        assert set(result.data['accepted_categories'])==CATEGORIES
        assert 'Correct category and retry' in result.error_message
    with pytest.raises(InvalidMemoryCategory):
        memory.store.remember('Visit Edinburgh',category=category)
    with pytest.raises(InvalidMemoryCategory):
        memory.create_proposal('Visit Edinburgh',category=category)
    with memory.store.connection() as db:
        for table in ('memories','memory_proposals','memory_sources','memory_revisions','memory_index_outbox','memory_fts'):
            assert db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


@pytest.mark.parametrize('content,category,scope',[
    ('Użytkownik chce w przyszłości odwiedzić Edynburg.','goal','user'),
    ('Użytkownik woli spokojne wycieczki.','preference','user'),
    ('Użytkownik interesuje się historią Szkocji.','interest','user'),
    ('Użytkownik potrafi programować w Pythonie.','skill','user'),
    ('Użytkownik chce zostać architektem oprogramowania.','goal','user'),
    ('Projekt używa SQLite jako źródła prawdy.','decision','project'),
])
def test_explicit_proposals_deduplicate_and_require_review(memory,content,category,scope):
    tool=MemoryTool(memory,'project-a')
    args=dict(content=content,category=category,scope=scope)
    first=tool.call('propose',**args)
    assert first.success and first.data['status']=='pending_review'
    assert not memory.store.list_memories('project-a')
    assert tool.call('propose',**args).data['proposal_id']==first.data['proposal_id']
    assert len(memory.proposals('project-a'))==1
    key=memory.decide(first.data['proposal_id'],True)['memory_id']
    assert memory.store.get(key)['category']==category
    assert tool.call('propose',**args).data['status']=='already_remembered'
    assert len(memory.store.list_memories('project-a'))==1


@pytest.mark.parametrize('native',[False,True])
@pytest.mark.parametrize('category',list(CATEGORY_DESCRIPTIONS)+['goals'])
def test_extraction_uses_same_schema_and_normalization(memory,native,category):
    chat=conversation(5)
    chat['events'][0]['content']='I want to visit Edinburgh'
    memory.enqueue(chat,{'provider':'fixture','model':'fixture'})
    payload=json.dumps({'candidates':[dict(content='I want to visit Edinburgh',category=category,
        scope='user',event_id='u0',evidence='I want to visit Edinburgh',confirmed=True,
        operation='create',target_id=None)]})
    def generate(messages,**kwargs):
        assert all(name in messages[0].content for name in CATEGORIES)
        return SimpleNamespace(content=payload)
    def generate_tools(messages,model,definitions):
        schema=definitions[0]['parameters']['properties']['candidates']['items']['properties']['category']
        assert set(schema['enum'])==CATEGORIES
        from laew.llm.base import ToolCall
        return SimpleNamespace(tool_calls=[ToolCall('extract','memory_candidates',payload)])
    provider=SimpleNamespace(native_tools=native,generate=generate,generate_tools=generate_tools)
    assert memory.process_extraction(SimpleNamespace(load_conversation=lambda _:chat),lambda _:(provider,'fixture'))
    assert memory.proposals()[0]['category']==normalize_category(category)
    assert not memory.store.list_memories()


def test_review_revalidates_invalid_persisted_category(memory):
    proposal=memory.create_proposal('Untrusted proposal')
    with memory.store.transaction() as db:
        db.execute('UPDATE memory_proposals SET category=? WHERE id=?',('personal',proposal))
    with pytest.raises(InvalidMemoryCategory): memory.decide(proposal,True)
    assert not memory.store.list_memories()
    assert memory.proposals()[0]['status']=='pending'


@pytest.mark.parametrize('provider_type',['ollama','llama.cpp'])
def test_local_adapters_present_contract_and_allow_corrected_call(memory,monkeypatch,provider_type):
    import copy
    from laew.agent import Agent,AgentConfig,AgentExecutor
    from laew.llm.ollama import OllamaProvider
    from laew.llm.llamacpp import LlamaCppProvider
    from laew.security.permissions import PermissionBroker
    contents=[]
    for category in ('personal','goals'):
        contents.append('```tool_call\n'+json.dumps(dict(tool='MemoryTool',operation='propose',
            args=dict(content='Visit Edinburgh',scope='user',category=category)))+'\n```')
    contents.append('Proposal ready for review.')
    responses=iter(contents);requests=[]
    def post(url,**kwargs):
        requests.append(copy.deepcopy(kwargs['json']))
        content=next(responses)
        data=({'message':{'content':content}} if provider_type=='ollama' else
              {'choices':[{'message':{'content':content},'finish_reason':'stop'}]})
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)
    monkeypatch.setattr('requests.post',post)
    provider=OllamaProvider() if provider_type=='ollama' else LlamaCppProvider('fixture')
    monkeypatch.setattr(provider,'is_available',lambda:True)
    broker=PermissionBroker(None)
    result=AgentExecutor(Agent(AgentConfig(model='fixture'),provider=provider,tools=[MemoryTool(memory)])).run(
        'Remember that I want to visit Edinburgh',on_tool_call=lambda t,op,args:broker.call(t,op,args,None))
    assert result.success and not result.steps[0].tool_result.success
    assert result.steps[1].tool_result.success
    assert all(name in requests[0]['messages'][0]['content'] for name in CATEGORIES)
    assert 'accepted_categories' in json.dumps(requests[1])
    assert memory.proposals()[0]['category']=='goal'
    assert not memory.store.list_memories()


def test_cli_category_contract(memory,monkeypatch,capsys):
    from laew.cli import cmd_memory
    monkeypatch.setattr('laew.cli.load_manifest',lambda _: {})
    monkeypatch.setattr('laew.memory.integration.build_memory',lambda *args:memory)
    args=SimpleNamespace(manifest='fixture.yaml',general=True,action='add',content='Visit Edinburgh',scope='user',category='personal')
    assert cmd_memory(args)==1
    output=capsys.readouterr().out
    assert all(category in output for category in CATEGORIES)
    assert not memory.store.list_memories()
    args.category='goals'
    assert cmd_memory(args)==0
    assert json.loads(capsys.readouterr().out)['category']=='goal'


def test_broker_preserves_category_error_and_denies_unbound_project(memory):
    from laew.security.permissions import PermissionBroker
    broker=PermissionBroker(None)
    args=dict(content='Visit Edinburgh',scope='user',category='personal')
    invalid=broker.call(MemoryTool(memory),'propose',args,None)
    assert not invalid.success and set(invalid.data['accepted_categories'])==CATEGORIES
    denied=broker.call(MemoryTool(memory,'other-project'),'propose',
        dict(content='Project decision',scope='project',category='decision'),None)
    assert not denied.success and denied.error_code=='ERR_UNAUTHORIZED'
    invalid_scope=MemoryTool(memory).call('propose',content='Project decision',scope='project',category='decision')
    assert not invalid_scope.success
    assert not memory.proposals('other-project') and not memory.store.list_memories('other-project')


def test_storage_failure_cannot_claim_a_successful_write(memory,monkeypatch):
    def fail(*args,**kwargs):raise OSError('unavailable')
    monkeypatch.setattr(memory,'create_proposal',fail)
    result=MemoryTool(memory).call('propose',content='Visit Edinburgh',scope='user',category='goal')
    assert not result.success and result.data is None
    assert not memory.proposals() and not memory.store.list_memories()
