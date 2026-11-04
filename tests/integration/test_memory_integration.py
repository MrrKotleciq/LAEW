"""Real Chroma indexing and application memory API, with disposable data only."""
import contextlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
from laew.memory.store import MemoryStore
from laew.memory.service import MemoryService
from laew.rag.vector_store import ChromaVectorStore
from laew.web import WorkspaceService


@pytest.mark.integration
def test_real_chroma_memory_recovery_filtering_and_rebuild(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    command=[sys.executable,'-c',"import sys; from chromadb.cli.cli import app; sys.argv[0]='chroma'; app()",'run','--host','127.0.0.1','--port',str(port),'--path',str(tmp_path/'chroma')]
    process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                if requests.get(f'http://127.0.0.1:{port}/api/v2/heartbeat',timeout=.5).ok:break
            except requests.RequestException:time.sleep(.2)
        else: pytest.fail('Disposable Chroma did not start')
        index=ChromaVectorStore(host='127.0.0.1',port=port,collection_name='memory_test_only',source='memory',embedding_model_id='fixture-2d')
        embedding=SimpleNamespace(embed=lambda text:[1.,0.] if 'Python' in text else [0.,1.])
        store=MemoryStore(tmp_path/'memory.db');memory=MemoryService(store,index_factory=lambda:index,embedding_factory=lambda:embedding)
        personal=store.remember('Prefers Python')
        project=store.remember('Python decision','project','a','decision')
        assert memory.sync_index()['processed']==2
        assert [row['id'] for row in memory.recall('Python')]==[personal['id']]
        assert project['id'] in {row['id'] for row in memory.recall('Python','a')}
        assert project['id'] not in {row['id'] for row in memory.recall('Python','b')}
        store.update(personal['id'],'Prefers Rust',1)
        assert not memory.recall('Python')
        memory.sync_index();assert memory.recall('Rust')[0]['version']==2
        store.delete(personal['id'],2);assert not memory.recall('Rust')
        memory.sync_index();assert personal['id'] not in index._collection.get()['ids']
        index._collection.delete(ids=[project['id']]);memory.sync_index(rebuild=True)
        assert index._collection.get()['ids']==[project['id']]
        # User -> real Chief/tool/broker -> SQLite -> review/auto -> real Chroma.
        from laew.agent import Agent,AgentConfig,AgentExecutor
        from laew.console.session_store import SessionStore
        from laew.llm.base import LLMResponse
        from laew.memory.tool import MemoryTool
        from laew.memory.store import identifier
        from laew.security.permissions import PermissionBroker
        for mode in ('review','auto'):
            root=tmp_path/mode
            sessions=SessionStore(root/'sessions')
            chat=sessions.create_conversation('general',None)
            store=MemoryStore(root/'memory.db');store.save_settings({'extraction_mode':mode})
            index=ChromaVectorStore(host='127.0.0.1',port=port,collection_name='memory_flow_'+mode,source='memory',embedding_model_id='fixture-2d')
            memory=MemoryService(store,index_factory=lambda:index,embedding_factory=lambda:embedding)
            content='Użytkownik chce w przyszłości odwiedzić Edynburg.'
            class Chief:
                def is_available(self):return True
                def generate(self,messages,**kwargs):
                    if messages[-1].role.value=='user' and 'Tool ' not in messages[-1].content:
                        call={'tool':'MemoryTool','operation':'propose','args':dict(content=content,category='goal',scope='user')}
                        return LLMResponse('```tool_call\n'+json.dumps(call)+'\n```','fixture')
                    return LLMResponse('Proposal ready for review.','fixture')
            broker=PermissionBroker(None)
            tool=MemoryTool(memory,conversation_id=chat['id'])
            result=AgentExecutor(Agent(AgentConfig(model='fixture'),provider=Chief(),tools=[tool])).run(
                'Zapamiętaj, że chcę w przyszłości odwiedzić Edynburg.',
                on_event=lambda e:sessions.append_conversation_event(chat['id'],{**e,'run_id':'explicit'}),
                on_tool_call=lambda t,op,args:broker.call(t,op,args,None))
            assert result.success and result.steps[0].tool_result.success
            assert len(memory.proposals())==1 and not store.list_memories()
            assert index._collection.count()==0  # Explicit writes never bypass review, even in Auto.
            key=memory.decide(memory.proposals()[0]['id'],True)['memory_id']
            assert memory.sync_index()['processed']==1
            assert index._collection.get(ids=[key])['documents']==[content]
            assert memory.recall('Edynburg')[0]['category']=='goal'
            sessions.append_conversation_event(chat['id'],{'id':identifier(),'kind':'run','status':'completed','content':'','run_id':'explicit'})
            # Fresh, exactly evidenced category avoids the existing conservative Auto conflict gate.
            evidence='I am skilled at Python'
            user=sessions.append_conversation_event(chat['id'],{'id':identifier(),'kind':'user','status':'completed','content':evidence,'run_id':'extract'})
            sessions.append_conversation_event(chat['id'],{'id':identifier(),'kind':'assistant','status':'completed','content':'Understood','run_id':'extract'})
            sessions.append_conversation_event(chat['id'],{'id':identifier(),'kind':'run','status':'completed','content':'','run_id':'extract'})
            assert memory.enqueue(sessions.load_conversation(chat['id']),{'provider':'fixture','model':'fixture'},manual=True)
            candidate=dict(content=evidence,category='skill',scope='user',event_id=user['id'],evidence=evidence,
                           confirmed=True,operation='create',target_id=None)
            extractor=SimpleNamespace(generate=lambda *a,**kw:SimpleNamespace(content=json.dumps({'candidates':[candidate]})))
            assert memory.process_extraction(sessions,lambda _:(extractor,'fixture'))
            if mode=='review':
                assert len(store.list_memories())==1 and len(memory.proposals())==1
                memory.decide(memory.proposals()[0]['id'],True)
            else:
                assert len(store.list_memories())==2 and not memory.proposals()
            assert memory.sync_index()['processed']==1
            assert index._collection.count()==2
            assert 'skill' in {row['category'] for row in memory.recall('Python')}
    finally:
        process.terminate();process.wait(timeout=20)


def test_application_memory_settings_inheritance_and_scope(tmp_path):
    projects=tmp_path/'Projects';project=projects/'A';project.mkdir(parents=True)
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'memory':{'session':{'storage':str(tmp_path/'sessions')}}}))
    # Patch manifest parsing at the composition boundary; the API still uses real SQLite/files.
    from unittest.mock import patch
    with patch('laew.web.load_manifest',return_value={'memory':{'session':{'storage':str(tmp_path/'sessions')}}}):
        service=WorkspaceService(manifest,project_root=project,projects_root=projects)
        service._memory=MemoryService(MemoryStore(tmp_path/'memory.db'))
        service._memory_worker=SimpleNamespace(request=lambda **kwargs:None)
        project_id=service._id_for_path(project)
        assert service.application_settings({'defaults':{'documentation_language':'pl'}})[0]==200
        body=service.application_settings({'project_id':project_id})[1]
        assert body['effective']['documentation_language']=='pl'
        assert body['overrides']=={}
        assert service.application_settings({'project_id':project_id,'overrides':{'documentation_language':'en'},'memory_overrides':{'recall_enabled':False}})[0]==200
        assert not service._memory.store.settings(project_id)['recall_enabled']
        assert service._memory.store.settings()['recall_enabled']
        first=service.memory_request('add',{'content':'User fact','scope':'user','category':'fact'})[1]
        scoped=service.memory_request('add',{'content':'Project fact','scope':'project','project_id':project_id,'category':'fact'})[1]
        assert service.memory_request('get',{'id':scoped['id']})[0]==400
        assert service.memory_request('get',{'id':scoped['id'],'project_id':project_id})[0]==200
        assert service.memory_request('get',{'id':first['id']})[0]==200
        assert service.memory_request('add',{'content':'Bad','scope':'project','project_id':'unknown','category':'fact'})[0]==400
        from laew.memory.categories import CATEGORIES
        assert set(service.memory_request('state',{})[1]['categories'])==CATEGORIES
        bad=service.memory_request('add',{'content':'Visit Edinburgh','scope':'user','category':'personal'})
        assert bad[0]==400 and set(bad[1]['accepted_categories'])==CATEGORIES
        assert bad[1]['retryable'] is True
        good=service.memory_request('add',{'content':'Visit Edinburgh','scope':'user','category':'goals'})
        assert good[0]==200 and good[1]['category']=='goal'
        assert service.application_settings({'project_id':project_id,'overrides':{'documentation_language':None}})[1]['effective']['documentation_language']=='pl'
