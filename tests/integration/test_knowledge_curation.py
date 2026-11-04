"""Curation end-to-end against disposable Chroma, vault and conversations."""
import json
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
import requests

from laew.console.session_store import SessionStore
from laew.knowledge.service import KnowledgeCurationService
from laew.knowledge.tool import KnowledgeProposalTool
from laew.prompts.context_budget import ContextBudget
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.pipeline import RAGPipeline
from laew.rag.rag_tool import RagTool
from laew.rag.sync import synchronize_scope
from laew.security.path_resolver import PathResolver
from laew.security.permissions import PermissionBroker
from laew.tools.filesystem import FilesystemTool


class EmbeddingFixture:
    dimensions = 3
    model = 'knowledge-isolated-fixture'

    def embed(self, text):
        return [1., .2, .1]

    def embed_batch(self, texts):
        return [self.embed(text) for text in texts]


@pytest.fixture
def disposable_chroma(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    command = [sys.executable, '-c',
        "import sys; from chromadb.cli.cli import app; sys.argv[0]='chroma'; app()",
        'run', '--host', '127.0.0.1', '--port', str(port), '--path', str(tmp_path/'chroma')]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                if requests.get(f'http://127.0.0.1:{port}/api/v2/heartbeat', timeout=.5).ok:
                    break
            except requests.RequestException:
                time.sleep(.2)
        else:
            pytest.fail('Disposable Chroma did not start')
        yield port
    finally:
        process.terminate()
        process.wait(timeout=15)


@pytest.mark.integration
def test_approved_create_update_rejection_duplicate_and_index_recovery(tmp_path, disposable_chroma):
    vault = tmp_path/'Knowledge'
    projects = tmp_path/'Projects'
    projects.mkdir()
    for folder in ('topics', 'research'):
        (vault/folder).mkdir(parents=True)
    sessions = SessionStore(tmp_path/'sessions')
    chat = sessions.create_conversation('general', None)
    evidence = 'Validated online identification procedure: persist the sampling interval and report measurement noise.'
    event = sessions.append_conversation_event(chat['id'],
        {'id': 'source-1', 'kind': 'user', 'status': 'completed', 'content': evidence, 'run_id': 'r1'})
    sessions.append_conversation_event(chat['id'],
        {'id': 'end-1', 'kind': 'run', 'status': 'completed', 'content': '', 'run_id': 'r1'})
    embedding = EmbeddingFixture()
    kb = KnowledgeBase(None, str(vault), embedding, chunk_size=200, chunk_overlap=20,
        vector_store_config={'enabled': True, 'host': '127.0.0.1', 'port': disposable_chroma,
                             'global_collection': 'knowledge_curation_test_only'})
    outage = [False]
    def sync(path):
        if outage[0]:
            raise RuntimeError('Simulated transport outage')
        return synchronize_scope(kb, 'global')
    filesystem = FilesystemTool(PathResolver(projects_root=projects, knowledge_root=vault, general=True))
    make = lambda: KnowledgeCurationService(tmp_path/'curation.db', sessions, filesystem,
        lambda scope: PermissionBroker(None), sync)
    service = make()
    # Independent detector, using the real completed-turn persistence and mocked model transport.
    candidate = {'title': 'Online Identification', 'summary': 'Reusable validated technical procedure.',
        'content': evidence, 'event_id': event['id'], 'evidence': evidence,
        'classification': 'global_knowledge', 'source_type': 'user_fact', 'verification': 'confirmed'}
    extractor = SimpleNamespace(generate=lambda *args, **kwargs:
        SimpleNamespace(content=json.dumps({'candidates': [candidate]})))
    assert service.enqueue(sessions.load_conversation(chat['id']), {'provider': 'fixture', 'model': 'fixture'}, manual=True)
    assert service.process_extraction(sessions, lambda selection: (extractor, 'fixture'))
    proposal = service.list_proposals()[0]
    assert not list((vault/'topics').glob('*.md'))
    assert service.preview(proposal['id'])['content']
    written = service.decide(proposal['id'], None, proposal['version'], 'approve')
    assert written['status'] == 'applied' and written['index_status'] == 'pending'
    note = filesystem.knowledge_note_path(written['target'])
    assert evidence in note.read_text(encoding='utf-8')
    service = make()  # Restart preserves the write and pending index work.
    assert service.sync_index()['indexed'] == 1
    pipeline = RAGPipeline(kb, embedding, similarity_threshold=0)
    pipeline.require_freshness = True
    rag = RagTool(pipeline, ContextBudget(), global_only=True)
    found = rag.call('query', query='sampling measurement noise', scope='global')
    assert found.success and evidence[:30] in str(found.data)
    tool = KnowledgeProposalTool(service, conversation_id=chat['id'], event_id=event['id'])
    repeated = tool.call('propose_create', title=candidate['title'], summary=candidate['summary'],
        content=evidence, evidence=evidence, source_type='user_fact', verification='confirmed')
    assert repeated.success and repeated.data['status'] == 'already_covered'
    update = service.create_proposal('Sampling Update', 'New test evidence.',
        'Validated refinement: normalize residuals before updating parameters.', chat['id'], [event['id']],
        kind='update', target=written['target'], source_type='test_result', verification='confirmed', evidence=evidence)
    assert '+Validated refinement' in service.preview(update['id'])['diff']
    old_ids = set(kb.global_store._collection.get()['ids'])
    service.decide(update['id'], None, update['version'], 'approve')
    outage[0] = True
    assert service.sync_index()['indexed'] == 0
    assert 'normalize residuals' in note.read_text(encoding='utf-8')
    outage[0] = False
    service = make()
    assert service.sync_index()['indexed'] == 1
    assert 'normalize residuals' in str(rag.call('query', query='residuals', scope='global').data)
    indexed = kb.global_store.sync_records('global')
    assert len({chunk.chunk_id for chunk in indexed}) == len(indexed)
    assert set(kb.global_store._collection.get()['ids']) >= old_ids
    rejected = service.create_proposal('Rejected Algorithm', 'Unverified alternative.',
        'Rejected content must never become searchable.', chat['id'], [event['id']],
        source_type='inference', verification='needs_verification')
    service.decide(rejected['id'], None, rejected['version'], 'reject')
    service.sync_index()
    assert not filesystem.knowledge_note_path(rejected['target']).exists()
    assert all('Rejected content' not in chunk.text for chunk in kb.global_store.sync_records('global'))
