"""Isolated curation lifecycle, evidence, permissions and retry regression tests."""
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from laew.knowledge.service import KnowledgeCurationService
from laew.knowledge.tool import KnowledgeProposalTool
from laew.security.path_resolver import PathResolver
from laew.security.permissions import PermissionBroker
from laew.tools.filesystem import FilesystemTool


@pytest.fixture
def curation(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    for folder in ('topics', 'research', 'inbox', 'templates', '.obsidian', '.smart-env'):
        (vault / folder).mkdir()
    conversations = {'general': {'id': 'general', 'project_id': None, 'events': [
        {'id': 'user1', 'kind': 'user', 'content': 'We measured repeatable sampling behavior with this procedure.', 'sequence': 0, 'run_id': 'r1'},
        {'id': 'answer1', 'kind': 'assistant', 'content': 'Possible explanation.', 'sequence': 1, 'run_id': 'r1'},
        {'id': 'done1', 'kind': 'run', 'status': 'completed', 'sequence': 2, 'run_id': 'r1'}]},
        'project': {'id': 'project', 'project_id': 'alpha', 'events': [
            {'id': 'project-user', 'kind': 'user', 'content': 'Reusable numerical procedure outside this project.', 'sequence': 0, 'run_id': 'pr1'},
            {'id': 'project-done', 'kind': 'run', 'status': 'completed', 'sequence': 1, 'run_id': 'pr1'}]}}
    session_store = SimpleNamespace(load_conversation=lambda key: conversations[key])
    fs = FilesystemTool(PathResolver(projects_root=tmp_path / 'projects', knowledge_root=vault, general=True))
    indexed = []
    service = KnowledgeCurationService(tmp_path / 'curation.db', session_store, fs,
        lambda project: PermissionBroker(None), lambda path: indexed.append(path))
    service.fixture_vault = vault
    service.fixture_indexed = indexed
    service.fixture_conversations = conversations
    return service


def propose(service, **kwargs):
    args = {'title': 'Repeatable sampling', 'summary': 'Preserve a reusable technical procedure.',
            'content': 'Measure the response at a fixed interval and record the observed variance.',
            'conversation_id': 'general', 'event_ids': ['user1'], 'verification': 'confirmed',
            'evidence': 'We measured repeatable sampling behavior'}
    return service.create_proposal(**(args | kwargs))


def note(title='Existing note', body='Original content with [[related]].', newline='\n'):
    return ('---\nname: ' + title + '\ndescription: Existing metadata\ntype: docs\nscope: global\nstatus: active\ntags: []\ncustom: keep\n---\n\n# ' + title + '\n\n' + body + '\n').replace('\n', newline)


def test_review_write_index_and_idempotent_approval(curation):
    row = propose(curation)
    path = curation._path(row['target'])
    assert not path.exists()
    assert 'scope: global' in curation.preview(row['id'])['markdown']
    applied = curation.decide(row['id'], None, row['version'], 'approve')
    assert applied['status'] == 'applied' and applied['index_status'] == 'pending'
    assert path.read_bytes().decode() == row['content']
    assert not curation.fixture_indexed
    assert curation.decide(row['id'], None, row['version'], 'approve')['status'] == 'applied'
    assert curation.sync_index() == {'indexed': 1}
    assert curation.get(row['id'])['index_status'] == 'indexed'
    assert curation.sync_index() == {'indexed': 0}


def test_reject_and_defer_persist_without_write(curation):
    row = propose(curation)
    deferred = curation.decide(row['id'], None, row['version'], 'defer')
    restarted = KnowledgeCurationService(curation.store.path, curation.conversations, curation.filesystem,
        curation.broker_factory, curation.sync_callback)
    assert restarted.get(row['id'])['status'] == 'deferred'
    restarted.decide(row['id'], None, deferred['version'], 'reject')
    restarted.sync_index()
    assert not curation._path(row['target']).exists()
    assert not curation.fixture_indexed


def test_proposal_dedup_and_existing_duplicate(curation):
    first = propose(curation)
    assert propose(curation)['id'] == first['id']
    curation.decide(first['id'], None, first['version'], 'approve')
    assert propose(curation)['status'] == 'already_covered'


def test_update_preserves_bytes_metadata_sections_and_replaces_via_broker(curation):
    path = curation.fixture_vault / 'topics' / 'existing.md'
    original = note(newline='\r\n')
    path.write_bytes(original.encode())
    row = propose(curation, title='New information', kind='update', target='@knowledge/topics/existing.md')
    assert row['base_content'] == original
    assert 'Original content' in row['content'] and 'custom: keep' in row['content']
    assert '+Measure the response' in curation.preview(row['id'])['diff']
    assert curation.decide(row['id'], None, row['version'], 'approve')['status'] == 'applied'


def test_stale_target_and_stale_review_do_not_overwrite(curation):
    path = curation.fixture_vault / 'topics' / 'existing.md'
    path.write_text(note(), encoding='utf-8')
    row = propose(curation, title='New information', kind='update', target='@knowledge/topics/existing.md')
    path.write_text(note(body='Newer edit'), encoding='utf-8')
    assert curation.preview(row['id'])['stale']
    with pytest.raises(ValueError, match='Target changed'):
        curation.decide(row['id'], None, row['version'], 'approve')
    assert 'Newer edit' in path.read_text()
    edited = curation.edit(row['id'], None, row['version'], row['content'] + '\nExtra\n')
    with pytest.raises(ValueError, match='Proposal changed'):
        curation.decide(row['id'], None, row['version'], 'approve')
    assert edited['version'] > row['version']


@pytest.mark.parametrize('target', ['@knowledge/../escape.md', '@knowledge/.obsidian/change.md',
    '@knowledge/.smart-env/change.md', '@knowledge/inbox/new.md', '@knowledge/templates/new.md',
    '@project/new.md', '@knowledge/topics/new.py'])
def test_unsafe_or_excluded_paths(curation, target):
    with pytest.raises(ValueError):
        curation._path(target)


def test_scoped_sources_and_queue(curation):
    with pytest.raises(ValueError, match='outside'):
        propose(curation, conversation_id='project', event_ids=['project-user'])
    row = propose(curation, conversation_id='project', event_ids=['project-user'], project_id='alpha', evidence='Reusable numerical procedure')
    assert curation.list_proposals() == []
    assert curation.list_proposals('alpha')[0]['id'] == row['id']
    with pytest.raises(ValueError, match='scope'):
        curation.get(row['id'])


@pytest.mark.parametrize('content', ['Bearer abcdefghijklmnop', 'api_key=abcdefghijklmnop', 'password: abcdefghijklmnop'])
def test_secrets_rejected_before_persistence(curation, content):
    with pytest.raises(ValueError, match='Credentials'):
        propose(curation, content=content)
    assert curation.list_proposals() == []


def test_secret_in_source_rejected(curation):
    curation.fixture_conversations['general']['events'][0]['content'] = 'token=abcdefghijklmnop'
    with pytest.raises(ValueError, match='Credentials'):
        propose(curation)


def test_unverified_assistant_not_confirmed_fact(curation):
    with pytest.raises(ValueError, match='user source'):
        propose(curation, event_ids=['answer1'])
    with pytest.raises(ValueError, match='verification'):
        propose(curation, source_type='assistant_suggestion')


def test_ambiguous_match_requires_explicit_choice(curation):
    existing = curation.fixture_vault / 'topics' / 'repeatable-sampling.md'
    existing.write_text(note('Repeatable sampling', 'Different technical details.'), encoding='utf-8')
    row = propose(curation, title='Repeatable sampling procedure')
    assert row['needs_target_decision']
    with pytest.raises(ValueError, match='matching notes'):
        curation.decide(row['id'], None, row['version'], 'approve')
    converted = curation.edit(row['id'], None, row['version'], row['content'], target='@knowledge/topics/repeatable-sampling.md', kind='update')
    assert converted['proposal_type'] == 'update'
    assert 'Different technical details.' in converted['content']
    assert curation.decide(row['id'], None, converted['version'], 'approve')['status'] == 'applied'


def test_chroma_failure_retry_and_restart_recovery(curation):
    row = propose(curation)
    curation.decide(row['id'], None, row['version'], 'approve')
    def unavailable(path):
        raise ConnectionError('offline')
    curation.sync_callback = unavailable
    curation.sync_index()
    assert curation.get(row['id'])['index_status'] == 'pending'
    assert curation._path(row['target']).exists()
    restarted = KnowledgeCurationService(curation.store.path, curation.conversations, curation.filesystem,
        curation.broker_factory, lambda path: None)
    assert restarted.sync_index()['indexed'] == 1
    assert restarted.get(row['id'])['index_status'] == 'indexed'


def test_restricted_permission_denies_write(curation):
    curation.broker_factory = lambda project: PermissionBroker(None, mode='restricted')
    row = propose(curation)
    result = curation.decide(row['id'], None, row['version'], 'approve')
    assert result['status'] == 'failed'
    assert not curation._path(row['target']).exists()


def test_concurrent_approval_one_artifact(curation):
    row = propose(curation)
    def approve(_):
        try:
            return curation.decide(row['id'], None, row['version'], 'approve')['status']
        except ValueError:
            return 'refresh'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(approve, range(2)))
    assert 'applied' in outcomes
    assert len(list(curation.fixture_vault.rglob('*.md'))) == 1


def test_tool_proposes_without_write_and_rejects_arbitrary_operations(curation):
    tool = KnowledgeProposalTool(curation, conversation_id='general', event_id='user1')
    args = {'title': 'Numerical method', 'summary': 'Reusable numerical method.', 'content': 'Keep the measured variance.' ,
            'source_type': 'user_fact', 'verification': 'confirmed', 'evidence': 'We measured repeatable sampling behavior'}
    result = tool.call('propose_create', **args)
    assert result.success and result.data['status'] == 'pending_review'
    assert not list(curation.fixture_vault.rglob('*.md'))
    assert not tool.call('approve', proposal_id=result.data['proposal_id']).success
    assert not tool.call('propose_create', **args, file_path='@knowledge/topics/evil.md').success


def test_bounded_extraction_checkpoint_and_memory_classification(curation):
    curation.save_settings({'interval_completed_turns': 2})
    conversation = curation.fixture_conversations['general']
    assert curation.enqueue(conversation, {'provider': 'fixture', 'model': 'test'}) is None
    key = curation.enqueue(conversation, {'provider': 'fixture', 'model': 'test'}, manual=True)
    assert key
    assert curation.enqueue(conversation, {'provider': 'fixture', 'model': 'test'}, manual=True) is None
    candidate = {'classification': 'memory', 'content': 'User likes music'}
    provider = SimpleNamespace(generate=lambda *args, **kwargs: SimpleNamespace(content=json.dumps({'candidates': [candidate]})))
    assert curation.process_extraction(curation.conversations, lambda selection: (provider, 'fixture'))
    assert curation.list_proposals() == []
    assert curation.enqueue(conversation, {'provider': 'fixture', 'model': 'test'}, manual=True) is None


@pytest.mark.parametrize('classification', ['global_knowledge', 'needs_verification'])
def test_automatic_candidate_with_real_evidence(curation, classification):
    conversation = curation.fixture_conversations['general']
    assert curation.enqueue(conversation, {'provider': 'fixture', 'model': 'test'}, manual=True)
    candidate = {'classification': classification, 'title': 'Measured procedure', 'summary': 'Reusable measured technique.',
                 'content': 'Record repeatable sampling behavior and compare variance.', 'event_id': 'user1',
                 'evidence': 'We measured repeatable sampling behavior', 'source_type': 'user_fact', 'verification': 'needs_verification'}
    provider = SimpleNamespace(generate=lambda *args, **kwargs: SimpleNamespace(content=json.dumps({'candidates': [candidate]})))
    assert curation.process_extraction(curation.conversations, lambda selection: (provider, 'fixture'))
    assert curation.list_proposals()[0]['status'] == 'pending_review'
    assert not list(curation.fixture_vault.rglob('*.md'))


def test_automatic_analysis_never_retroactively_backfills_baseline(curation):
    conversation = curation.fixture_conversations['general']
    curation.baseline(conversation)
    assert curation.enqueue(conversation, {'provider': 'fixture', 'model': 'test'}, manual=True) is None


def test_cannot_enable_automatic_publication(curation):
    with pytest.raises(ValueError, match='requires review'):
        curation.save_settings({'auto_write': True})
