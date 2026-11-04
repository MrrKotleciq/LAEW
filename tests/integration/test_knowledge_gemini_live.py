"""Opt-in Gemini smoke test with a synthetic conversation and no vault writes."""
import os

import pytest

from laew.cloud_chat import CloudChatService
from laew.console.session_store import SessionStore
from laew.knowledge.service import KnowledgeCurationService
from laew.security.path_resolver import PathResolver
from laew.tools.filesystem import FilesystemTool


@pytest.mark.live
@pytest.mark.skipif(os.environ.get('LAEW_TEST_KNOWLEDGE_GEMINI') != '1',
                    reason='Requires explicit opt-in for a Gemini API request.')
def test_gemini_flash_lite_extracts_reviewable_knowledge(tmp_path):
    vault, projects = tmp_path / 'Knowledge', tmp_path / 'Projects'
    projects.mkdir()
    (vault / 'topics').mkdir(parents=True)
    (vault / 'research').mkdir()
    sessions = SessionStore(tmp_path / 'conversations')
    chat = sessions.create_conversation('general', None)
    filesystem = FilesystemTool(PathResolver(projects_root=projects, knowledge_root=vault, general=True))

    def forbidden(*args):
        pytest.fail('Extraction must never write or index a proposal.')

    service = KnowledgeCurationService(tmp_path / 'curation.db', sessions, filesystem, forbidden, forbidden)
    service.baseline(sessions.load_conversation(chat['id']))
    inputs = [
        'Lubię kolor zielony.',
        'Co by się stało, gdyby czujnik był idealny?',
        'W powtarzalnych testach identyfikacji ARX potwierdziłem, że stały okres próbkowania i rozdzielenie danych kalibracji od walidacji zmniejszają błąd oceny modelu. Procedura: rejestruję okres próbkowania, dopasowuję ARX wyłącznie na zbiorze kalibracji i raportuję błąd reszt na niezależnym przebiegu.',
        'Wynik był powtarzalny na trzech niezależnych przebiegach. Tę procedurę stosuję również do innych obiektów dynamicznych.',
        'Dziękuję za rozmowę.',
    ]
    for i, content in enumerate(inputs):
        run = f'run-{i}'
        sessions.append_conversation_event(chat['id'], {'id': f'user-{i}', 'kind': 'user',
            'status': 'completed', 'content': content, 'run_id': run})
        sessions.append_conversation_event(chat['id'], {'id': f'end-{i}', 'kind': 'run',
            'status': 'completed', 'content': '', 'run_id': run})
    model = 'gemini-3.5-flash-lite'
    assert service.enqueue(sessions.load_conversation(chat['id']), {'provider': 'gemini', 'model': model})
    cloud = CloudChatService()
    try:
        provider = cloud.provider('gemini', timeout=30)
        class CheckedProvider:
            def generate(self, messages, **kwargs):
                try:
                    return provider.generate(messages, **kwargs)
                except Exception as exc:
                    pytest.fail(f'Gemini request failed: {type(exc).__name__}: {exc}')
        assert service.process_extraction(sessions, lambda selection: (CheckedProvider(), selection['model']))
    finally:
        cloud.close()
    rows = service.list_proposals()
    assert rows and all(row['status'] == 'pending_review' for row in rows)
    assert any('ARX' in row['content'] for row in rows)
    assert all(set(row['source_event_ids']) <= {'user-2', 'user-3'} for row in rows)
    assert not list(vault.rglob('*.md'))
