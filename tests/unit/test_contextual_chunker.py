"""Context preservation invariants independent of retrieval embeddings."""
import pytest
from laew.rag.contextual_chunker import contextual_chunks
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.pipeline import RAGPipeline
from laew.rag.sync import synchronize_scope, freshness_error
from tests.unit.test_markdown_chunker import Embedding


@pytest.mark.parametrize('body', [
    '# Root\n## Init\nFirst connect.\n```python\nconnect()\n```\nNever skip validation.\n',
    '# Firmware\nDisconnect actuator before starting.\n## Procedure\n' + '1. Verify supply.\n' * 150,
    '# Table\nNominal values, not maximum ratings.\n| Name | Offset (mV) |\n| --- | --- |\n' + '| sensor | 41 |\n'*120 + 'Never use as alarm thresholds.\n',
    '# Root\n## Empty\n### Child\n> Quote [[Link]]\n' + 'x'*8000 + '\n~~~python\nunclosed()',
])
def test_partition_bounds_and_provenance(body):
    chunks = contextual_chunks(body, 300)
    assert ''.join(body[c.start_offset:c.end_offset] for c in chunks) == body
    assert all(0 < len(c.text) <= 300 for c in chunks)
    assert all(c.text[c.synthetic_chars:] == body[c.start_offset:c.end_offset] for c in chunks)
    assert all(0 <= a < z <= len(body) for c in chunks for a,z in c.context_spans)
    assert all(c.start_line == body[:c.start_offset].count('\n')+1 for c in chunks)
    assert all(c.end_line == body[:c.end_offset-1].count('\n')+1 for c in chunks)
    assert all(c.synthetic_chars < 300//2 for c in chunks)


def test_small_description_code_and_warning_stay_together():
    text = '# Device\n## Initialization\nConnect before enabling.\n```python\nconnect()\nenable()\n```\nThis avoids stale commands.\n'
    chunks = contextual_chunks(text, 1000)
    assert len(chunks) == 1
    assert chunks[0].text == text and chunks[0].language == 'python'
    assert chunks[0].path == ('Device', 'Initialization')


def test_prerequisites_survive_later_procedure_chunks():
    text = '# Update\nDisconnect actuator before starting.\n## Procedure\n'+'1. Upload and verify.\n'*100
    chunks = contextual_chunks(text, 400)
    assert all('Disconnect actuator before starting.' in c.text for c in chunks if c.start_offset > 400)


@pytest.mark.parametrize('scope', ['global', 'project'])
def test_strategy_transition_failures_rollback_and_sources(tmp_path, monkeypatch, scope):
    project=tmp_path/'project'; project.mkdir()
    vault=tmp_path/'vault'; vault.mkdir()
    emb=Embedding()
    kb=KnowledgeBase(str(project), str(vault), emb)
    root = vault if scope=='global' else project
    store = kb.global_store if scope=='global' else kb.project_store
    note=root/'note.md'; note.write_text('---\ntitle: Example\nstatus: draft\n---\n# Root\n## Data\nBody\n',encoding='utf8')
    for strategy in ['legacy','structure-v1','structure-v2','legacy']:
        kb.chunking_strategy=strategy
        synchronize_scope(kb,scope)
        assert freshness_error(kb,scope) is None
        records=store.sync_records(scope)
        assert len({r.chunk_id for r in records})==len(records)
        assert all(r.metadata.get('chunking_strategy','legacy')==strategy for r in records)
        result=RAGPipeline(kb,emb)._build_context([(records[0],1)])
        assert ('@knowledge' if scope=='global' else '@project') in result[0]
    kb.chunking_strategy='structure-v2'
    assert 'strategy changed' in freshness_error(kb,scope)
    synchronize_scope(kb,scope)
    for content in ['# Changed\n```sh\nchanged\n```','## Table\n| A | B |\n| --- | --- |\n| a | b |','## Short\nx']:
        note.write_text(content,encoding='utf8'); synchronize_scope(kb,scope)
        assert all('Body' not in r.text for r in store.sync_records(scope))
    calls=len(emb.inputs); synchronize_scope(kb,scope)
    assert len(emb.inputs)==calls
    note.write_text('# New\nnew',encoding='utf8')
    original_delete=store.delete_ids
    monkeypatch.setattr(store,'delete_ids',lambda ids: (_ for _ in ()).throw(RuntimeError('partial failure')))
    with pytest.raises(RuntimeError): synchronize_scope(kb,scope)
    assert freshness_error(kb,scope)
    monkeypatch.setattr(store,'delete_ids',original_delete)
    synchronize_scope(kb,scope)
    assert all('Short' not in r.text for r in store.sync_records(scope))
    note.unlink(); synchronize_scope(kb,scope)
    assert not store.sync_records(scope)
