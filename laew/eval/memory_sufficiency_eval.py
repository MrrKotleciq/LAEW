"""Repeatable isolated Memory-to-RAG evaluation with a local-only CLI.

The adapter returns a fixed response. Model modes evaluate only the assessment
call, not Chief answer quality. RAG uses a local persistent test index and
synthetic, deterministic embeddings, not production retrieval or embeddings.
"""
import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.knowledge.horizon import HorizonAssessor
from laew.knowledge.routing import KnowledgeTurn
from laew.knowledge.sufficiency import configured_assessor
from laew.llm.base import LLMResponse
from laew.memory.service import MemoryService
from laew.memory.store import MemoryStore
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool
from laew.security.permissions import PermissionBroker

DATASET = Path('tests/evaluation/memory_sufficiency/validation.json')


class FixedAdapter:
    def __init__(self):
        self.messages = []
    def is_available(self):
        return True
    def generate(self, messages, **kwargs):
        self.messages.append(list(messages))
        return LLMResponse('Fixed evaluation response.', kwargs['model'])


class FixtureEmbedding:
    model = 'sufficiency-evaluation-onehot'
    def __init__(self, cases):
        self.cases = cases
        self.dimensions = len(cases)
        self.current = 0
    def vector(self, index):
        return [1.0 if i == index else 0.0 for i in range(self.dimensions)]
    def embed(self, text):
        return self.vector(self.current)
    def embed_batch(self, texts):
        result = []
        for text in texts:
            index = next((i for i, c in enumerate(self.cases) if f"EVIDENCE-{c['id']}" in text), None)
            if index is None:
                raise ValueError('Index chunk missing evaluation identifier')
            result.append(self.vector(index))
        return result


def local_provider(model, url):
    from laew.llm.llamacpp import LlamaCppProvider
    parsed = urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or parsed.username:
        raise ValueError('Only explicit loopback HTTP servers are allowed')
    return LlamaCppProvider(model=model, base_url=url, timeout=30)


def run_mode(name, cases, tool, embedding, scratch, assessor=None):
    rows = []
    broker = PermissionBroker(None)
    for index, case in enumerate(cases):
        embedding.current = index
        store = MemoryStore(scratch / f'{name}-{case["id"]}.db')
        store.save_settings({'semantic_enabled': False})
        for content in case['memory']:
            store.remember(content)
        memory = MemoryService(store)
        adapter = FixedAdapter()
        agent = Agent(AgentConfig(), provider=adapter, tools=[tool])
        executor = AgentExecutor(agent)
        turn = KnowledgeTurn(lambda t, op, args: broker.call(t, op, args, None), assessor=assessor)
        started = time.perf_counter()
        turn.prepare(executor, case['question'], None, lambda: memory, tool)
        result = executor.run(case['question'], on_tool_call=turn.call, on_diagnostic=turn.observe,
                              on_tool_batch=turn.after_tools)
        elapsed = (time.perf_counter() - started) * 1000
        if not result.success:
            raise RuntimeError('Fixture adapter execution failed')
        diag = turn.diagnostics
        searches = diag['prefetch']
        model = diag.get('assessment', {}).get('model_assessment', {})
        supplied = '\n'.join(m.content for batch in adapter.messages for m in batch)
        rows.append({'id': case['id'], 'kind': case['kind'], 'needs_rag': case['needs_rag'],
            'rag_calls': sum(bool(s.get('search_executed')) for s in searches),
            'assessment_status': diag.get('assessment', {}).get('status'),
            'assessment_reason': diag.get('assessment', {}).get('reason'),
            'model_status': model.get('status'), 'model_error': model.get('error_category'),
            'horizon_signal': model.get('signal'), 'horizon_entailment': model.get('entailment_score'),
            'model_calls': model.get('calls', 0), 'assessment_ms': model.get('elapsed_ms', 0),
            'prompt_tokens': model.get('prompt_tokens'), 'completion_tokens': model.get('completion_tokens'),
            'retrieval_ms': sum(s.get('elapsed_ms', 0) for s in searches), 'end_to_end_ms': round(elapsed, 2),
            'memory_requested': diag['memory_requested'], 'initial_scopes': diag['initial_scopes'],
            'routing_reason': diag['reason'], 'memory_status': diag['memory_recall']['status'],
            'memory_supplied': diag['memory_recall'].get('supplied', 0),
            'rag_supplied': sum(s.get('supplied', 0) for s in searches),
            'context_characters': len(supplied),
            'evidence_covered': (case['evidence'] in supplied) if case['evidence'] else None})
    required = [r for r in rows if r['needs_rag']]
    optional = [r for r in rows if not r['needs_rag']]
    scored = [r for r in rows if r['evidence_covered'] is not None]
    metrics = {
        'cases': len(rows), 'rag_required': len(required), 'rag_unnecessary_candidates': len(optional),
        'false_sufficient': sum(r['assessment_status'] == 'sufficient' for r in required),
        'unnecessary_rag': sum(bool(r['rag_calls']) for r in optional),
        'missed_required_rag': sum(not r['rag_calls'] for r in required),
        'missed_evidence': sum(not r['evidence_covered'] for r in scored),
        'evidence_covered': sum(bool(r['evidence_covered']) for r in scored),
        'evidence_scored': len(scored),
        'rag_calls': sum(r['rag_calls'] for r in rows), 'assessment_calls': sum(r['model_calls'] for r in rows),
        'assessment_ms': round(sum(r['assessment_ms'] for r in rows), 2),
        'retrieval_ms': round(sum(r['retrieval_ms'] for r in rows), 2),
        'end_to_end_ms': round(sum(r['end_to_end_ms'] for r in rows), 2),
        'model_errors': sum(r['model_status'] == 'failed' for r in rows),
        'prompt_tokens': sum(r['prompt_tokens'] or 0 for r in rows),
        'completion_tokens': sum(r['completion_tokens'] or 0 for r in rows),
        'token_usage_missing_calls': sum(r['model_calls'] and (r['prompt_tokens'] is None or r['completion_tokens'] is None) for r in rows),
    }
    return {'status': 'completed', 'metrics': metrics, 'cases': rows}


def evaluate(cases, settings, *, horizon=False, additional_assessors=()):
    """Evaluate the fixtures. API callers can explicitly inject comparison assessors."""
    import chromadb
    import laew.rag.vector_store as vector_store
    with tempfile.TemporaryDirectory(prefix='.memory-eval-', dir='.') as folder:
        root = Path(folder).resolve()
        vault, projects = root / 'knowledge', root / 'projects'
        vault.mkdir(); projects.mkdir()
        for case in cases:
            (vault / (case['id'] + '.md')).write_text(f"EVIDENCE-{case['id']} {case['rag']}", encoding='utf-8')
        client = chromadb.PersistentClient(path=str(root / 'chroma'))
        original = vector_store._build_chroma_client
        vector_store._build_chroma_client = lambda *args: client
        try:
            manifest = {'rag': {'vector_store': {'enabled': True, 'global_collection': 'eval_' + uuid4().hex}}}
            embedding = FixtureEmbedding(cases)
            rag = build_rag_tool(manifest, project_root=None, projects_root=projects, knowledge_root=vault,
                                 embedding_service=embedding, general=True)
            synchronize_scope(rag._pipeline.knowledge_base, 'global')
            results = {'heuristic': run_mode('heuristic', cases, rag, embedding, root)}
            if horizon:
                results['horizon'] = run_mode('horizon', cases, rag, embedding, root, HorizonAssessor())
            for name, assessor in additional_assessors:
                results[name] = run_mode(name, cases, rag, embedding, root, assessor)
            for mode in ('active', 'dedicated'):
                model, url = settings[mode]
                if not model:
                    results[mode] = {'status': 'not_run', 'reason': 'No verified local model ID was supplied.'}
                    continue
                provider = local_provider(model, url)
                try:
                    available = provider.list_models()
                except Exception as exc:
                    results[mode] = {'status': 'not_run', 'reason': type(exc).__name__, 'model': model, 'endpoint': url}
                    continue
                if model not in available:
                    results[mode] = {'status': 'not_run', 'reason': 'Model ID absent from server catalog.', 'model': model, 'endpoint': url}
                    continue
                active = SimpleNamespace(provider=provider, config=SimpleNamespace(model=model))
                if mode == 'active':
                    config = {'memory_sufficiency': {'enabled': True, 'model': 'active'}}
                else:
                    config = {'memory_sufficiency': {'enabled': True, 'model': {'provider': 'llama.cpp', 'model': model}},
                              'agent': {'llm': {'providers': [{'type': 'llama.cpp', 'base_url': url}]}}}
                assessor = configured_assessor(config, active)
                results[mode] = run_mode(mode, cases, rag, embedding, root, assessor)
                results[mode].update(model=model, endpoint=url)
            return results
        finally:
            vector_store._build_chroma_client = original
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Output JSON path; do not use a production data directory')
    parser.add_argument('--dataset', type=Path, default=DATASET)
    parser.add_argument('--horizon', action='store_true', help='Evaluate the local Horizon endpoint in isolation')
    parser.add_argument('--active-model')
    parser.add_argument('--active-url', default='http://127.0.0.1:8080')
    parser.add_argument('--dedicated-model')
    parser.add_argument('--dedicated-url', default='http://127.0.0.1:8080')
    args = parser.parse_args()
    data = args.dataset.read_bytes()
    cases = json.loads(data.decode('utf-8-sig'))
    result = {'dataset': str(args.dataset), 'dataset_sha256': hashlib.sha256(data).hexdigest(),
              'limitations': ['synthetic corpus and embeddings', 'fixed response adapter, no Chief answer scoring',
                              'isolated FTS Memory and persistent test Chroma', 'single measured pass'],
              'results': evaluate(cases, {'active': (args.active_model, args.active_url),
                                           'dedicated': (args.dedicated_model, args.dedicated_url)}, horizon=args.horizon)}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({name: run.get('metrics', run) for name, run in result['results'].items()}, indent=2))


if __name__ == '__main__':
    main()
