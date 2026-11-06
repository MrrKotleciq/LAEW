import pytest
from laew.rag.markdown_chunker import structure_chunks
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import DocumentChunk


class Embedding:
    model = 'structure-test'
    dimensions = 3
    def __init__(self):
        self.inputs = []
    def embed_batch(self, texts):
        self.inputs.extend(texts)
        return [[1., 0., 0.] for _ in texts]


def test_complex_markdown_is_bounded_and_source_spans_partition_input():
    body = ('# System Architecture\n## Memory\n### Automatic Recall\n'
            'Opis prerequisite [[Link|alias]].\n1. Start\n   - nested\n2. End\n'
            '```python\n# not a heading\n' + 'print("zażółć")\n' * 40 + '```\n'
            '| Name | Value |\n| --- | --- |\n' + ''.join(f'| item{i} | {i} |\n' for i in range(40))
            + '> quote\nUnclosed:\n~~~sql\nSELECT 1;\n# still code\n')
    chunks = structure_chunks(body, 120)
    assert ''.join(body[c.start_offset:c.end_offset] for c in chunks) == body
    assert all(len(c.text) <= 120 for c in chunks)
    assert all(c.path == ('System Architecture', 'Memory', 'Automatic Recall') for c in chunks if c.kind in ('code', 'table'))
    assert any(c.language == 'python' for c in chunks)
    tables = [c for c in chunks if c.kind == 'table']
    assert len(tables) > 1 and all('| Name | Value |' in c.text for c in tables)
    assert all(c.repeated_prefix == '' or c.kind == 'table' for c in chunks)


def test_empty_and_oversized_lines():
    assert structure_chunks('', 64) == []
    body = 'x' * 500
    chunks = structure_chunks(body, 64)
    assert ''.join(c.text for c in chunks) == body
    assert all(len(c.text) <= 64 for c in chunks)
    with pytest.raises(ValueError):
        structure_chunks(body, 10)


@pytest.mark.parametrize('scope', ['global', 'project'])
def test_versioned_sync_replaces_old_records_and_preserves_metadata(tmp_path, scope):
    project = tmp_path / 'project'; project.mkdir()
    vault = tmp_path / 'vault'; vault.mkdir()
    emb = Embedding()
    kb = KnowledgeBase(str(project), str(vault), emb, chunk_size=100, chunk_overlap=10)
    root = vault if scope == 'global' else project
    store = kb.global_store if scope == 'global' else kb.project_store
    note = root / 'note.md'
    note.write_text('---\ntitle: Example\nstatus: draft\ntags: [test]\n---\n# Parent\n## Child\nEnglish i polski.\n', encoding='utf8')
    kb.synchronize(scope=scope)
    old = {r.chunk_id for r in store.sync_records(scope)}
    kb.chunking_strategy = 'structure-v1'
    kb.synchronize(scope=scope)
    records = store.sync_records(scope)
    assert records and old.isdisjoint({r.chunk_id for r in records})
    child = next(r for r in records if r.metadata['section_header'] == 'Child')
    assert child.metadata['section_path'] == ['Parent', 'Child']
    assert child.metadata['frontmatter']['status'] == 'draft'
    assert any('Parent > Child' in item for item in emb.inputs)
    context, _, _ = RAGPipeline(kb, emb)._build_context([(child, 1)])
    assert 'Parent > Child' in context
    calls = len(emb.inputs)
    kb.synchronize(scope=scope)
    assert len(emb.inputs) == calls
    note.write_text('# New\nreplacement', encoding='utf8')
    kb.synchronize(scope=scope)
    assert all('Child' not in r.text for r in store.sync_records(scope))
    kb.chunking_strategy = 'legacy'
    kb.synchronize(scope=scope)
    assert all('structure-v1' not in r.chunk_id for r in store.sync_records(scope))


def test_structure_failure_keeps_old_index_and_load_refuses_mixed_versions(tmp_path):
    project = tmp_path / 'project'; project.mkdir()
    vault = tmp_path / 'vault'; vault.mkdir()
    emb = Embedding()
    kb = KnowledgeBase(str(project), str(vault), emb)
    note = vault / 'note.md'
    note.write_text('# Original\nbody', encoding='utf8')
    kb.synchronize(scope='global')
    before = [(r.chunk_id, r.text) for r in kb.global_store.sync_records('global')]
    kb.chunking_strategy = 'structure-v1'
    kb._vault_loaded = False
    with pytest.raises(RuntimeError, match='requires synchronization'):
        kb.load_vault()
    def fail(texts):
        raise RuntimeError('offline')
    emb.embed_batch = fail
    with pytest.raises(RuntimeError, match='Failed to embed'):
        kb.synchronize(scope='global')
    assert [(r.chunk_id, r.text) for r in kb.global_store.sync_records('global')] == before
