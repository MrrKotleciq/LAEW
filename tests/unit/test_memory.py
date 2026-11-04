"""Isolated source-of-truth, scope and review regression tests."""
import pytest
from laew.memory.store import MemoryStore
from laew.memory.service import MemoryService


def test_memory_lifecycle_and_restart(tmp_path):
    store=MemoryStore(tmp_path/'memory.db')
    first=store.remember('Prefers Python',category='preference',source={'conversation_id':'c','event_id':'e'})
    assert store.remember('Prefers Python',category='preference')['id']==first['id']
    revised=store.update(first['id'],'Prefers Rust',1)
    assert revised['version']==2 and len(revised['revisions'])==2 and len(revised['sources'])==1
    with pytest.raises(ValueError): store.update(first['id'],'Stale',1)
    store=MemoryStore(tmp_path/'memory.db')
    assert store.get(first['id'])['content']=='Prefers Rust'
    assert len(store.fts('Rust',None))==1
    store.delete(first['id'],2)
    assert not store.fts('Rust',None)
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM memory_index_outbox').fetchone()[0]==3


def test_scope_and_review(tmp_path):
    store=MemoryStore(tmp_path/'memory.db'); service=MemoryService(store)
    store.remember('Python project A','project','a')
    store.remember('Python project B','project','b')
    store.remember('Python user')
    assert len(store.fts('Python',None))==1
    assert len(store.fts('Python','a'))==2
    proposal=service.create_proposal('Likes electronics',source={'conversation_id':'c','event_id':'e'})
    assert not store.fts('electronics',None)
    service.decide(proposal,True)
    assert len(store.fts('electronics',None))==1
    with pytest.raises(ValueError): service.decide(proposal,True)
    with pytest.raises(ValueError): store.remember('bad','user','a')


def test_fallback_settings_and_atomic_failed_update(tmp_path):
    store=MemoryStore(tmp_path/'memory.db'); service=MemoryService(store)
    original=store.remember('Prefers Python')
    assert service.recall('Python')[0]['id']==original['id']
    assert service.retrieval_mode=='FTS5 fallback'
    assert service.sync_index().get('error')
    with pytest.raises(ValueError): store.save_settings({'extraction_mode':'invalid'})
    assert store.settings()['extraction_mode']=='review'
    store.save_settings({'recall_enabled':False})
    assert not service.recall('Python')
    assert MemoryStore(tmp_path/'memory.db').settings()['recall_enabled'] is False


def test_proposal_version_conflict_rolls_back(tmp_path):
    store=MemoryStore(tmp_path/'memory.db'); service=MemoryService(store)
    memory=store.remember('Fifth semester',category='education')
    proposal=service.create_proposal('Sixth semester',category='education',target_id=memory['id'])
    store.update(memory['id'],'Seventh semester',1)
    with pytest.raises(ValueError): service.decide(proposal,True)
    assert service.proposals()[0]['status']=='pending'
    assert store.get(memory['id'])['content']=='Seventh semester'


def conversation(turns):
    events=[]
    for i in range(turns):
        events.extend([{'id':f'u{i}','sequence':len(events),'kind':'user','content':'I prefer Python','run_id':str(i)},
                       {'id':f'a{i}','sequence':len(events)+1,'kind':'assistant','content':'Understood','run_id':str(i)},
                       {'id':f'r{i}','sequence':len(events)+2,'kind':'run','content':'','status':'completed','run_id':str(i)}])
    return {'id':'conversation','project_id':None,'events':events}


def test_extraction_interval_checkpoint_and_review(tmp_path):
    import json
    from types import SimpleNamespace
    store=MemoryStore(tmp_path/'memory.db'); service=MemoryService(store)
    assert service.enqueue(conversation(4),{'provider':'test','model':'test'}) is None
    assert service.enqueue(conversation(5),{'provider':'test','model':'test'})
    assert service.enqueue(conversation(5),{'provider':'test','model':'test'}) is None
    output={'candidates':[{'content':'Prefers Python','category':'preference','scope':'user','event_id':'u0','evidence':'I prefer Python','confirmed':True,'target_id':None}]}
    class Provider:
        def generate(self,*args,**kwargs): return SimpleNamespace(content=json.dumps(output))
    sessions=SimpleNamespace(load_conversation=lambda key:conversation(5))
    assert service.process_extraction(sessions,lambda selection:(Provider(),'test'))
    assert not store.list_memories()
    proposals=service.proposals(); assert len(proposals)==1
    assert service.enqueue(conversation(5),{}) is None
    with store.connection() as db:
        assert db.execute('SELECT sequence FROM extraction_checkpoints').fetchone()[0]==14
    service.decide(proposals[0]['id'],True)
    assert len(store.list_memories())==1


def test_failed_extraction_keeps_job_and_checkpoint(tmp_path):
    from types import SimpleNamespace
    store=MemoryStore(tmp_path/'memory.db'); service=MemoryService(store)
    service.enqueue(conversation(5),{'provider':'test','model':'test'})
    class Provider:
        def generate(self,*args,**kwargs): return SimpleNamespace(content='not JSON')
    assert service.process_extraction(SimpleNamespace(load_conversation=lambda key:conversation(5)),lambda selection:(Provider(),'test')) is False
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM extraction_checkpoints').fetchone()[0]==0
        assert db.execute('SELECT status FROM extraction_jobs').fetchone()[0]=='pending'
    assert not store.list_memories()


def test_concurrent_exact_writes_and_atomic_outbox(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    store=MemoryStore(tmp_path/'memory.db')
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(lambda _:store.remember('One durable fact')['id'],range(8)))
    assert len(set(ids))==1
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM memories').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM memory_index_outbox').fetchone()[0]==1


class Collection:
    def __init__(self): self.rows={}; self.failure=False
    def upsert(self,ids,documents,embeddings,metadatas):
        if self.failure: raise ConnectionError('offline')
        for key,text,meta in zip(ids,documents,metadatas): self.rows[key]=(text,meta)
    def query(self,**kwargs):
        if self.failure: raise ConnectionError('offline')
        return {'ids':[list(self.rows)],'metadatas':[[row[1] for row in self.rows.values()]],'distances':[[.1]*len(self.rows)]}


def indexed_service(tmp_path):
    from types import SimpleNamespace
    collection=Collection()
    index=SimpleNamespace(_collection=collection,delete_ids=lambda ids:[collection.rows.pop(key,None) for key in ids])
    embedding=SimpleNamespace(embed=lambda text:[1.,0.])
    store=MemoryStore(tmp_path/'memory.db')
    return store,MemoryService(store,index_factory=lambda:index,embedding_factory=lambda:embedding),collection


def test_index_outbox_retry_stale_deleted_and_scope_validation(tmp_path):
    store,service,index=indexed_service(tmp_path)
    first=store.remember('Python preference')
    other=store.remember('Python secret B','project','b')
    index.failure=True
    assert service.sync_index().get('error')
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM memory_index_outbox WHERE completed_at IS NULL').fetchone()[0]==2
    index.failure=False
    assert service.sync_index()['processed']==2
    assert [row['id'] for row in service.recall('Python',None)]==[first['id']]
    store.update(first['id'],'Rust preference',1)
    assert not service.recall('Python',None)  # Old index version is never returned.
    service.sync_index()
    assert service.recall('Rust',None)[0]['version']==2
    store.delete(first['id'],2)
    assert not service.recall('Rust',None)
    service.sync_index(); assert first['id'] not in index.rows
    index.rows.clear();service.sync_index(rebuild=True)
    assert set(index.rows)=={other['id']}


def test_project_memory_settings_inherit_individually(tmp_path):
    store=MemoryStore(tmp_path/'memory.db')
    store.save_project_settings('a',{'recall_enabled':False,'extraction_model':None})
    store.save_settings({'max_memories':3,'interval_completed_turns':8,'extraction_model':{'provider':'gemini','model':'fixed-test-model'}})
    assert store.settings('a')['extraction_model'] is None
    assert store.settings('b')['extraction_model']['model']=='fixed-test-model'
    assert store.settings('a')['recall_enabled'] is False
    assert store.settings('b')['recall_enabled'] is True
    assert store.settings('a')['interval_completed_turns']==8
    assert store.settings('a')['max_memories']==3
    store.save_project_settings('a',{})
    assert store.settings('a')['recall_enabled'] is True
    with pytest.raises(ValueError): store.save_project_settings('a',{'token_budget':3})


def test_recall_context_budget_and_disabled_scope(tmp_path):
    store,service,_=indexed_service(tmp_path)
    for i in range(8): store.remember('Prefers Python for useful task '+str(i))
    service.sync_index()
    selected=service.recall('Python')
    assert len(selected)<=5
    assert len(service.context(selected).encode())<=400
    store.save_project_settings('a',{'recall_enabled':False})
    assert service.recall('Python','a')==[]
    assert service.recall('Python','b')


def test_enrollment_ignores_old_history_and_cancelled_runs(tmp_path):
    store=MemoryStore(tmp_path/'memory.db');service=MemoryService(store)
    service.baseline(conversation(8))
    assert service.enqueue(conversation(8),{}) is None
    assert service.enqueue(conversation(12),{}) is None
    assert service.enqueue(conversation(13),{'provider':'test','model':'test'})
    other=conversation(5);other['id']='cancelled';other['events'][-1]['status']='cancelled'
    assert service.enqueue(other,{}) is None


def test_unknown_schema_rejected(tmp_path):
    import sqlite3
    path=tmp_path/'future.db'
    with sqlite3.connect(path) as db: db.execute('PRAGMA user_version=999')
    with pytest.raises(ValueError): MemoryStore(path)


@pytest.mark.parametrize('category',['preference','education','interest','skill','goal','decision','constraint','fact'])
def test_review_categories_remain_pending_until_approval(tmp_path,category):
    import json
    from types import SimpleNamespace
    store=MemoryStore(tmp_path/'memory.db');service=MemoryService(store)
    service.enqueue(conversation(5),{'provider':'test','model':'test'})
    candidate={'content':'Prefers Python','category':category,'scope':'user','event_id':'u0','evidence':'I prefer Python','confirmed':True,'target_id':None}
    provider=SimpleNamespace(generate=lambda *args,**kwargs:SimpleNamespace(content=json.dumps({'candidates':[candidate]})))
    assert service.process_extraction(SimpleNamespace(load_conversation=lambda key:conversation(5)),lambda selection:(provider,'test'))
    assert len(service.proposals())==1
    assert not store.list_memories()


@pytest.mark.parametrize('change',[
    {'event_id':'assistant-event'}, {'evidence':'invented evidence'}, {'confirmed':False},
    {'scope':'project'}, {'category':'unknown'}, {'operation':'update','target_id':'invented'},
    {'content':'Bearer abc123456789'},
])
def test_invalid_or_unsupported_candidates_cannot_advance_checkpoint(tmp_path,change):
    import json
    from types import SimpleNamespace
    store=MemoryStore(tmp_path/'memory.db');service=MemoryService(store)
    service.enqueue(conversation(5),{'provider':'test','model':'test'})
    candidate={'content':'Prefers Python','category':'preference','scope':'user','event_id':'u0','evidence':'I prefer Python','confirmed':True,'target_id':None,**change}
    provider=SimpleNamespace(generate=lambda *args,**kwargs:SimpleNamespace(content=json.dumps({'candidates':[candidate]})))
    assert not service.process_extraction(SimpleNamespace(load_conversation=lambda key:conversation(5)),lambda selection:(provider,'test'))
    assert not service.proposals()
    with store.connection() as db: assert db.execute('SELECT COUNT(*) FROM extraction_checkpoints').fetchone()[0]==0


def test_manual_off_empty_result_and_restart_retry(tmp_path):
    from types import SimpleNamespace
    store=MemoryStore(tmp_path/'memory.db');service=MemoryService(store)
    store.save_settings({'extraction_mode':'off'})
    assert service.enqueue(conversation(5),{}) is None
    assert service.enqueue(conversation(5),{'provider':'test','model':'test'},manual=True)
    unavailable=lambda selection:(_ for _ in ()).throw(TimeoutError())
    assert not service.process_extraction(SimpleNamespace(load_conversation=lambda key:conversation(5)),unavailable)
    with store.transaction() as db:db.execute('UPDATE extraction_jobs SET retry_at=0,lease_until=0')
    restarted=MemoryService(MemoryStore(tmp_path/'memory.db'))
    provider=SimpleNamespace(generate=lambda *args,**kwargs:SimpleNamespace(content='{"candidates":[]}'))
    assert restarted.process_extraction(SimpleNamespace(load_conversation=lambda key:conversation(5)),lambda selection:(provider,'test'))
    assert not restarted.proposals()
    with store.connection() as db:assert db.execute('SELECT sequence FROM extraction_checkpoints').fetchone()[0]==14


def test_model_context_is_not_persisted_as_user_history(tmp_path):
    from laew.agent import Agent,AgentConfig,AgentExecutor
    from laew.llm.base import LLMProvider,LLMResponse,MessageRole
    class Provider(LLMProvider):
        def is_available(self):return True
        def list_models(self):return ['test']
        def generate(self,messages,model,**kwargs):
            self.messages=messages[:];return LLMResponse('Hello','test')
    provider=Provider();agent=Agent(AgentConfig(model='test'),provider=provider,tools=[])
    executor=AgentExecutor(agent);executor.memory_context='Stored preference: Python'
    assert executor.run('Hello').success
    assert 'Stored preference: Python' in provider.messages[0].content
    assert all('Stored preference' not in message.content for message in agent.history)
    assert [message.role for message in agent.history]==[MessageRole.USER,MessageRole.ASSISTANT]


@pytest.mark.parametrize('mode,existing_count,expected_active,expected_pending',[
    ('auto',0,1,0),('auto',1,1,1),('review',0,0,1),('off',0,0,0)])
def test_auto_review_and_off_commit_policies(tmp_path,mode,existing_count,expected_active,expected_pending):
    import json
    from types import SimpleNamespace
    store=MemoryStore(tmp_path/'memory.db');service=MemoryService(store)
    store.save_settings({'extraction_mode':mode})
    if existing_count:store.remember('I prefer Rust',category='preference')
    job=service.enqueue(conversation(5),{'provider':'test','model':'test'})
    if mode=='off':assert job is None;return
    candidate={'content':'I prefer Python','category':'preference','scope':'user','event_id':'u0','evidence':'I prefer Python','confirmed':True,'target_id':None}
    provider=SimpleNamespace(generate=lambda *args,**kwargs:SimpleNamespace(content=json.dumps({'candidates':[candidate]})))
    assert service.process_extraction(SimpleNamespace(load_conversation=lambda key:conversation(5)),lambda selection:(provider,'test'))
    assert len(store.list_memories())==expected_active
    assert len(service.proposals())==expected_pending


def test_extraction_cannot_overwrite_a_target_changed_during_model_call(tmp_path):
    import json
    from types import SimpleNamespace
    store=MemoryStore(tmp_path/'memory.db');service=MemoryService(store)
    original=store.remember('I prefer Rust',category='preference')
    service.enqueue(conversation(5),{'provider':'test','model':'test'})
    def generate(*args,**kwargs):
        store.update(original['id'],'I prefer C++',1)
        return SimpleNamespace(content=json.dumps({'candidates':[{'content':'I prefer Python','category':'preference','scope':'user','event_id':'u0','evidence':'I prefer Python','confirmed':True,'target_id':original['id'],'operation':'update'}]}))
    assert not service.process_extraction(SimpleNamespace(load_conversation=lambda key:conversation(5)),lambda selection:(SimpleNamespace(generate=generate),'test'))
    assert store.get(original['id'])['content']=='I prefer C++'
    assert not service.proposals()
def test_recall_tool_validates_scope_status_and_fallback(tmp_path):
    from types import SimpleNamespace
    from laew.memory.tool import MemoryTool
    from laew.security.permissions import PermissionBroker

    store = MemoryStore(tmp_path / "memory.db")
    user = store.remember("Edinburgh travel preference", category="goal")
    own = store.remember("Edinburgh plan for this project", "project", "current", "goal")
    other = store.remember("Edinburgh confidential destination", "project", "other", "goal")
    deleted = store.remember("Edinburgh deleted memory", category="goal")
    store.delete(deleted["id"], deleted["version"])
    # A semantic response containing stale and out-of-scope hits must trigger the lexical fallback.
    collection = SimpleNamespace(query=lambda **_: {
        "ids": [[deleted["id"], other["id"]]], "metadatas": [[{"version": 1}, {"version": 1}]],
        "distances": [[0.1, 0.2]],
    })
    service = MemoryService(store, index_factory=lambda: SimpleNamespace(_collection=collection),
                            embedding_factory=lambda: SimpleNamespace(embed=lambda _: [1.]))
    pending = service.create_proposal("Edinburgh pending proposal", category="goal")
    rejected = service.create_proposal("Edinburgh rejected proposal", category="goal")
    service.decide(rejected, False)
    general = PermissionBroker(None, "restricted")
    project = PermissionBroker(tmp_path, "restricted")
    user_tool = MemoryTool(service)
    project_tool = MemoryTool(service, "current")
    assert not general.call(project_tool, "recall", {"query": "Edinburgh"}, None).success
    assert not project.call(project_tool, "recall", {"query": "Edinburgh", "project_id": "other"}, None).success
    for query in ("", " " * 10, "x" * 1001, 123):
        assert not user_tool.call("recall", query=query).success
    for broker, tool, expected in [(general, user_tool, {user["id"]}),
                                   (project, project_tool, {user["id"], own["id"]})]:
        result = broker.call(tool, "recall", {"query": "Edinburgh"}, None)
        assert result.success
        assert {row["id"] for row in result.data["memories"]} == expected
        assert result.data["recall"]["fallback_reason"] == "no_valid_semantic_matches"
        assert pending not in str(result.data) and rejected not in str(result.data)
    store.save_settings({"recall_enabled": False})
    assert user_tool.call("recall", query="Edinburgh").error_code == "ERR_MEMORY_DISABLED"
    store.save_settings({"recall_enabled": True})
    result = user_tool.call("recall", query="pending")
    assert result.success and result.data["status"] == "no_results" and not result.data["memories"]
