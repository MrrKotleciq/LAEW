"""Frozen hard-case judgments and strategy-neutral evidence scoring."""
import hashlib
import json
from pathlib import Path
from laew.eval.rag_baseline import score_query
from laew.rag.vector_store import DocumentChunk


def test_hard_case_labels_frozen_and_resolve_to_sources():
    root=Path('tests/rag/hard_cases_v1')
    raw=(root/'dataset.json').read_text(encoding='utf8').encode()
    assert hashlib.sha256(raw).hexdigest()=='462340ca7fcdc5f7ddd5447e68dde2afdb3baf6d5c718a93d7c71f8597975664'
    data=json.loads(raw)
    assert len({q['id'] for q in data['queries']})==13
    for q in data['queries']:
        for e in q['evidence']:
            assert e['passage'] in (root/'global'/e['document_id'].split('/',1)[1]).read_text(encoding='utf8')


def test_complete_evidence_requires_warning_as_well_as_value():
    query=dict(allowed_scope='global', no_answer=None,
        expected_document_ids=['@knowledge/note.md'],relevance={'@knowledge/note.md':2},
        evidence=[dict(document_id='@knowledge/note.md',passage='24 V'),dict(document_id='@knowledge/note.md',passage='Nominal only')])
    c=DocumentChunk('a','24 V',source='global',file_path='note.md')
    partial=score_query(query,[(c,1)],{'@knowledge/note.md'})
    assert partial['recall_at_5']==1 and partial['evidence_coverage']==.5 and not partial['complete_evidence']
    other=DocumentChunk('b','Nominal only',source='global',file_path='note.md')
    assert score_query(query,[(c,1),(other,.9)],{'@knowledge/note.md'})['complete_evidence']
