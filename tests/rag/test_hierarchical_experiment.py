"""Actual-Chroma drill-down and adversarial source/freshness tests."""
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from chromadb.errors import InternalError

from laew.eval.lexical_benchmark import DenseIndex
from laew.eval.hierarchical_benchmark import FrozenLease
from laew.rag.vector_store import DocumentChunk
from laew.rag.hierarchical_experiment import (
    Binding, Snapshot, ChromaDrillDown, UnsafeEvidence, kb_lease,
)


@pytest.fixture
def store(tmp_path):
    index=DenseIndex(tmp_path/'scratch-chroma',SimpleNamespace(scope='global'))
    records=[]
    # One correct source has a distant leaf; unrelated one-leaf documents
    # occupy most global seed slots. No semantic model or answer labels.
    for i in range(18):
        x=1.0 if i==0 else (.7 if i==17 else .9-i*.001)
        records.append({'id':f'c{i:02}','source':'global','path':'atlas.md' if i in (0,17) else f'{i}.md',
                        'text':f'unique leaf {i}','metadata':{'section_path':['Root',str(i)],'sync_fingerprint':'frozen'},
                        'embedding':[x,(1-x*x)**.5]})
    index.rebuild(records)
    snapshot=Snapshot.build(Binding(str(index.store._collection.id),'global'),'generation1',index.store.sync_records('global'))
    lease=FrozenLease('generation1')
    adapter=ChromaDrillDown(index.store._collection,snapshot,lease.lease)
    yield index,snapshot,lease,adapter
    index.close()


def test_actual_metadata_filter_recovers_distant_leaf_and_preserves_originals(store):
    index,snapshot,lease,adapter=store
    dense=adapter.retrieve([1,0])
    drill=adapter.retrieve([1,0],hierarchical=True)
    assert 'c17' not in [c.chunk_id for c,_ in dense.pairs]
    assert 'c17' in [c.chunk_id for c,_ in drill.pairs]
    assert len(drill.diagnostics['routed_documents'])==3
    assert drill.diagnostics['chroma_calls']==2
    assert len(drill.pairs)<=10
    assert len({c.chunk_id for c,_ in drill.pairs})==len(drill.pairs)
    assert sum(c.file_path=='atlas.md' for c,_ in drill.pairs)==2
    assert all(c.metadata['section_path'][0]=='Root' for c,_ in drill.pairs)
    assert drill.diagnostics['fetched_records']<=138
    assert drill.diagnostics['fetched_metadata_bytes']>0
    with patch.object(index.store._collection,'query',wraps=index.store._collection.query) as query:
        adapter.retrieve([1,0],hierarchical=True)
        where=query.call_args_list[1].kwargs['where']
        assert where['$and'][0]=={'source':'global'}
        assert where['$and'][1]['file_path']['$in']==['atlas.md','1.md','2.md']
        assert query.call_args_list[1].kwargs['n_results']==4


@pytest.mark.parametrize('failure',[OSError('unavailable'),NotImplementedError('filtered query unavailable'),InternalError('unavailable')])
def test_filtered_unavailable_falls_back_only_to_original_fresh_seeds(store,failure):
    index,snapshot,lease,adapter=store
    dense=adapter.retrieve([1,0])
    original=index.store._collection.query
    def query(**kwargs):
        if '$and' in kwargs['where']:
            raise failure
        return original(**kwargs)
    with patch.object(index.store._collection,'query',side_effect=query):
        result=adapter.retrieve([1,0],hierarchical=True)
    assert result.pairs==dense.pairs and result.diagnostics['fallback']


def test_missing_mapping_fallback_but_conflicting_mapping_fails(store):
    index,snapshot,lease,adapter=store
    missing=replace(snapshot,documents={})
    result=ChromaDrillDown(index.store._collection,missing,lease.lease).retrieve([1,0],hierarchical=True)
    assert result.pairs==result.seeds and 'missing_document_mapping' in result.diagnostics['fallback']
    conflict=replace(snapshot,documents={**snapshot.documents,'c00':'other.md'})
    with pytest.raises(UnsafeEvidence,match='Conflicting'):
        ChromaDrillDown(index.store._collection,conflict,lease.lease).retrieve([1,0],hierarchical=True)


@pytest.mark.parametrize('change',['text','file_path','source','metadata','id','distance'])
def test_stale_conflicting_or_unauthorized_results_never_degrade_to_dense(store,change):
    index,snapshot,lease,adapter=store
    original=index.store._collection.query
    def query(**kwargs):
        result=original(**kwargs)
        if '$and' in kwargs['where']:
            if change=='id': result['ids'][0][0]='unknown'
            elif change=='distance': result['distances'][0][0]=float('inf')
            elif change=='metadata': result['metadatas'][0][0]['sync_fingerprint']='"stale"'
            else: result['metadatas'][0][0][change]='project' if change=='source' else 'changed'
        return result
    with patch.object(index.store._collection,'query',side_effect=query),pytest.raises((UnsafeEvidence,ValueError)):
        adapter.retrieve([1,0],hierarchical=True)


@pytest.mark.parametrize('when',[1,2])
def test_generation_change_at_either_stage_fails_closed(store,when):
    index,snapshot,lease,adapter=store
    original=index.store._collection.query
    calls=0
    def query(**kwargs):
        nonlocal calls
        result=original(**kwargs);calls+=1
        if calls==when: lease.current='generation2'
        return result
    with patch.object(index.store._collection,'query',side_effect=query),pytest.raises(UnsafeEvidence,match='generation'):
        adapter.retrieve([1,0],hierarchical=True)


def test_outage_and_concurrent_generation_change_cannot_return_old_seeds(store):
    index,snapshot,lease,adapter=store
    original=index.store._collection.query
    def query(**kwargs):
        if '$and' in kwargs['where']:
            lease.current='changed'
            raise OSError('outage')
        return original(**kwargs)
    with patch.object(index.store._collection,'query',side_effect=query),pytest.raises(UnsafeEvidence):
        adapter.retrieve([1,0],hierarchical=True)


@pytest.mark.parametrize('mutation',['rename','delete'])
def test_real_mutations_require_new_generation_and_snapshot(store,mutation):
    index,snapshot,lease,adapter=store
    if mutation=='delete':
        index.store.delete_ids(['c00'])
    else:
        c=index.store.get_chunk('c00')
        index.store.add_chunk(DocumentChunk(c.chunk_id,c.text,[1.,0.],source='global',file_path='renamed.md',metadata=c.metadata))
    lease.current='new_generation'
    with pytest.raises(UnsafeEvidence): adapter.retrieve([1,0],hierarchical=True)
    fresh=Snapshot.build(snapshot.binding,'new_generation',index.store.sync_records('global'))
    current=FrozenLease('new_generation')
    result=ChromaDrillDown(index.store._collection,fresh,current.lease).retrieve([1,0],hierarchical=True)
    if mutation=='delete': assert 'c00' not in [c.chunk_id for c,_ in result.pairs]
    else: assert next(c.file_path for c,_ in result.pairs if c.chunk_id=='c00')=='renamed.md'


def test_duplicate_ids_across_scopes_and_projects_are_not_interchangeable(store,tmp_path):
    index,snapshot,lease,adapter=store
    other=DenseIndex(tmp_path/'project',SimpleNamespace(scope='project'))
    try:
        other.rebuild([{'id':'c00','source':'project','path':'atlas.md','text':'private', 'metadata':{},'embedding':[1.,0.]}])
        project=Snapshot.build(Binding(str(other.store._collection.id),'project',str(tmp_path/'ProjectA')),
                               'generation1',other.store.sync_records('project'))
        private=ChromaDrillDown(other.store._collection,project,lease.lease).retrieve([1,0],hierarchical=True)
        assert private.pairs[0][0].text=='private'
        assert adapter.retrieve([1,0]).pairs[0][0].text!='private'
        with pytest.raises(UnsafeEvidence,match='Collection'):
            ChromaDrillDown(other.store._collection,snapshot,lease.lease)
        kb=SimpleNamespace(project_root=tmp_path/'ProjectB')
        with pytest.raises(UnsafeEvidence,match='Project'):
            with kb_lease(kb,project): pass
    finally: other.close()


def test_existing_kb_generation_locks_are_held_across_both_queries(store):
    index,snapshot,lease,adapter=store
    class Lock:
        held=True
        def release(self): self.held=False
    lock=Lock()
    kb=SimpleNamespace(global_store=index.store)
    check=lambda *args:{'state':'successfully synchronized','generation':'generation1'}
    original=index.store._collection.query
    def query(**kwargs):
        assert lock.held
        return original(**kwargs)
    with patch('laew.rag.sync.acquire_fresh_scopes',return_value=([lock],None)),patch('laew.rag.sync.sync_status',side_effect=check),patch.object(index.store._collection,'query',side_effect=query):
        result=ChromaDrillDown(index.store._collection,snapshot,lambda:kb_lease(kb,snapshot)).retrieve([1,0],hierarchical=True)
    assert len(result.pairs)>0 and not lock.held
    with patch('laew.rag.sync.acquire_fresh_scopes',return_value=([],'freshness unknown')),pytest.raises(UnsafeEvidence,match='freshness'):
        with kb_lease(kb,snapshot): pass


def test_ties_and_duplicate_backend_ids_are_deterministic(store):
    index,snapshot,lease,adapter=store
    original=index.store._collection.query
    def query(**kwargs):
        result=original(**kwargs)
        result['distances'][0]=[.2]*len(result['ids'][0])
        for key in ('ids','metadatas','distances'): result[key][0].reverse()
        return result
    with patch.object(index.store._collection,'query',side_effect=query):
        result=adapter.retrieve([1,0])
    assert [c.chunk_id for c,_ in result.pairs]==sorted(c.chunk_id for c,_ in result.pairs)


def test_followup_read_depth_and_payload_memory_are_bounded(store):
    index,snapshot,lease,adapter=store
    bloated=replace(snapshot,counts={d:10000 for d in snapshot.counts})
    with patch.object(index.store._collection,'query',wraps=index.store._collection.query) as query:
        ChromaDrillDown(index.store._collection,bloated,lease.lease).retrieve([1,0],hierarchical=True)
        assert query.call_args.kwargs['n_results']==128
    with patch('laew.rag.hierarchical_experiment.RESPONSE_BYTES',1),pytest.raises(UnsafeEvidence,match='memory'):
        adapter.retrieve([1,0])


@pytest.mark.parametrize('path',['../secret.md','C:\\vault\\secret.md','/secret.md',''])
def test_snapshot_rejects_unsafe_logical_paths(path):
    with pytest.raises(UnsafeEvidence):
        Snapshot.build(Binding('collection','global'),'generation',[DocumentChunk('id','text',source='global',file_path=path)])
