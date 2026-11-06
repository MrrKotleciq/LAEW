"""Provider-neutral assessment and conservative fallback tests."""
from types import SimpleNamespace

import pytest

from laew.knowledge.routing import KnowledgeTurn, SourceRoute
from laew.knowledge.sufficiency import MemoryAssessor, configured_assessor
from laew.llm.base import LLMResponse


class Provider:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if isinstance(self.content, Exception):
            raise self.content
        return LLMResponse(self.content, kwargs['model'], prompt_tokens=31, completion_tokens=5)


@pytest.mark.parametrize('content,expected', [
    ('{"sufficient":true}', True), ('{"sufficient":false}', False),
    ('{"sufficient":"true"}', None), ('{"sufficient":true,"extra":1}', None),
    ('not json', None), (RuntimeError('private information'), None),
])
def test_response_validation_and_failure_fallback(content, expected):
    provider = Provider(content)
    assessor = MemoryAssessor(lambda: (provider, 'chosen-model'))
    turn = KnowledgeTurn(lambda *_: None, assessor=assessor)
    turn._decision = SourceRoute(True, (), 'test')
    turn._global_queries = set()
    turn.diagnostics = {'prefetch': []}
    turn._message = 'Which language did I study?'
    result, _, search, _ = turn._evaluate_recall(turn._message,
        {'status': 'completed', 'prepared': 1, 'mode': 'semantic'},
        [{'content': 'The user studied Spanish.'}])
    assert search is (expected is not True)
    assert result['status'] == ('sufficient' if expected is True else 'unverified')
    assert provider.calls[0][1]['model'] == 'chosen-model'
    assert 'private information' not in str(result)


def test_active_model_selection_tracks_provider():
    first, second = Provider('{}'), Provider('{}')
    agent = SimpleNamespace(provider=first, config=SimpleNamespace(model='first'))
    assessor = configured_assessor({'memory_sufficiency': {'enabled': True, 'model': 'active'}}, agent)
    assessor.assess('question', [{'content': 'answer'}])
    agent.provider, agent.config.model = second, 'second'
    assessor.assess('question', [{'content': 'answer'}])
    assert first.calls[0][1]['model'] == 'first'
    assert second.calls[0][1]['model'] == 'second'
    assert configured_assessor({}, agent) is None


def test_explicit_provider_selection(monkeypatch):
    chosen = Provider('{"sufficient":true}')
    selection = {'provider': 'gemini', 'model': 'chosen', 'account_id': 'test'}
    seen = []
    def factory(manifest, selected, cloud):
        seen.append((selected, cloud))
        return chosen, selected['model']
    monkeypatch.setattr('laew.memory.integration.extraction_provider', factory)
    assessor = configured_assessor({'memory_sufficiency': {'enabled': True, 'model': selection}}, None, 'cloud')
    assert assessor.assess('question', [{'content': 'answer'}])['sufficient']
    assert seen == [(selection, 'cloud')]

@pytest.mark.parametrize('route', [
    SourceRoute(True, (), 'memory only', memory_only=True, rag_disabled=True),
    SourceRoute(True, (), 'global excluded', excluded_scopes=('global',)),
    SourceRoute(True, ('global',), 'prefetch scheduled'),
])
def test_source_policy_avoids_unnecessary_assessment(route):
    provider = Provider('{"sufficient":true}')
    turn = KnowledgeTurn(lambda *_: None, assessor=MemoryAssessor(lambda: (provider, 'model')))
    turn._decision, turn._global_queries = route, set()
    turn.diagnostics = {'prefetch': []}
    turn._message = 'Which language did I study?'
    turn._evaluate_recall(turn._message, {'status': 'completed', 'prepared': 1},
                          [{'content': 'The user studied Spanish.'}])
    assert not provider.calls


def test_assessment_budget_is_one_request_per_turn():
    provider = Provider('{"sufficient":false}')
    turn = KnowledgeTurn(lambda *_: None, assessor=MemoryAssessor(lambda: (provider, 'model')))
    turn._decision, turn._global_queries = SourceRoute(True, (), 'test'), set()
    turn.diagnostics = {'prefetch': []}
    turn._message = 'Which language did I study?'
    recall = {'status': 'completed', 'prepared': 1}
    for _ in range(2):
        _, _, search, _ = turn._evaluate_recall(turn._message, recall, [{'content': 'Spanish.'}])
        assert search
    assert len(provider.calls) == 1
