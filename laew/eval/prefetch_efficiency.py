"""Measure isolated RAG retrieval and the prefetch tool budget on frozen fixtures."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from laew.eval import rag_baseline as baseline
from laew.prompts.context_budget import ContextBudget
from laew.rag.knowledge_base import KnowledgeScope
from laew.rag.rag_tool import RagTool, RetrievalOptions, retrieval_options


def evaluate(pipeline, dataset, sources):
    rows = []
    tool = RagTool(pipeline, ContextBudget())
    for query in dataset['queries']:
        scope = KnowledgeScope(query['allowed_scope'])
        row = {'id': query['id'], 'text': query['text'], 'scope': scope.value, 'runs': {}}
        for k in (1, 2, 5):
            start = time.perf_counter()
            result = pipeline.retrieve(query['text'], scope, top_k=k)
            if result.error:
                raise RuntimeError(result.error)
            row['runs'][str(k)] = {**baseline.score_query(query, result.chunks, sources),
                'elapsed_ms': (time.perf_counter() - start) * 1000,
                'tokens_estimated': result.total_tokens,
                'chunks': [{'id': c.chunk_id, 'document': baseline.document_id(c), 'score': s,
                            'text': c.text, 'section': c.metadata.get('section_header')}
                           for c, s in result.chunks]}
        # Automatic routing invokes each scope separately, rather than hybrid.
        scopes = ('project', 'global') if scope == KnowledgeScope.HYBRID else (scope.value,)
        contexts, diagnostics = [], []
        for name in scopes:
            options = RetrievalOptions(max_context_tokens=500)
            with retrieval_options(options):
                output = tool.execute('query', query=query['text'], scope=name, max_results=2)
            if not output.success:
                raise RuntimeError(output.error_message)
            contexts.append(output.data['context'])
            diagnostics.append({'scope': name, **options.diagnostics, 'context': output.data['context'],
                                'tokens_estimated': output.data['total_tokens']})
        def present(item):
            # Check the attributed section containing the passage, not a bare cross-document match.
            for d in diagnostics:
                alias = '@knowledge/' if d['scope'] == 'global' else '@project/'
                if not item['document_id'].startswith(alias):
                    continue
                path = item['document_id'][len(alias):]
                for part in d['context'].split('\n\n---\n\n'):
                    header, _, body = part.partition('\n')
                    if path in header and ('section' not in item or item['section'] in header):
                        if ' '.join(item['passage'].split()) in ' '.join(body.split()):
                            return True
            return False
        missing = [e for e in query['evidence'] if not present(e)]
        row['prefetch'] = {'scopes': diagnostics, 'missing_evidence': missing,
            'evidence_coverage': (1-len(missing)/len(query['evidence'])) if query['evidence'] else None,
            'complete_evidence': not missing if query['evidence'] else None,
            'tokens_estimated': sum(d['tokens_estimated'] for d in diagnostics)}
        rows.append(row)
    return {'queries': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--strategy', required=True, choices=('legacy', 'structure-v1', 'structure-v2'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with patch.object(baseline, 'evaluate', evaluate):
        report = baseline.run(Path('manifests/SYSTEM_MANIFEST.yaml'), args.dataset, args.strategy)
    report['experiment_utc'] = datetime.now(timezone.utc).isoformat()
    report['prefetch_note'] = 'Tool output; separate scopes, max_results=2, 500 estimated tokens per scope. Provider delivery requires integration verification.'
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
