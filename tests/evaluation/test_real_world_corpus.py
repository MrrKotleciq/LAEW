"""Opt-in offline admission checks for the external public corpus; no indexing."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'/'corpus'))
from audit_real_world import audit
from verify_corpus import verify


@pytest.fixture(scope='module')
def corpus():
    value=os.environ.get('LAEW_PUBLIC_CORPUS_ROOT')
    if not value:pytest.skip('Set LAEW_PUBLIC_CORPUS_ROOT to the external public-only staging root')
    root=Path(value).resolve()
    assert not root.is_relative_to(Path(r'C:\ROOT'))
    assert not any((p/'.obsidian').exists() for p in (root,*root.parents))
    return root,json.loads((root/'source-manifest.json').read_text(encoding='utf-8'))


def test_exact_proposed_units_and_source_integrity(corpus):
    root,manifest=corpus
    expected={f'prusa-{model}-{lang}' for model,lang in [('mk4s','en'),('mmu3','en'),('mk4','de'),('xl','de'),('mini','pl'),('mk3s','pl')]}
    expected|={f'progit-{topic}-{lang}' for topic in ['first-time-setup','config','remote-branches','submodules'] for lang in ['en','pl','de']}
    expected|={f'postgresql-{version}-{topic}' for version,topic in [('17','continuous-archiving'),('17','runtime-config-wal'),('17','backup'),('17','recovery-config'),('11','continuous-archiving'),('12','release-12')]}
    assert {u['id'] for u in manifest['source_units']}==expected
    assert len(manifest['source_units'])==24
    for u in manifest['source_units']:
        for pathkey,hashkey in [('original_path','original_sha256'),('normalized_path','normalized_sha256')]:
            raw=(root/u[pathkey]).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==u[hashkey]


def test_language_and_original_page_mappings(corpus):
    root,manifest=corpus
    for u in manifest['source_units']:
        body=(root/u['normalized_path']).read_text(encoding='utf-8')[u['body_offset']:]
        assert '\ufffd' not in body
        spans=json.loads((root/u['language_map']).read_text(encoding='utf-8'))
        assert spans[0]['start']==0 and spans[-1]['end']==len(body)
        assert all(a['end']==b['start'] for a,b in zip(spans,spans[1:]))
        if u['family']=='prusa':
            pages=json.loads((root/u['extraction']['page_map']).read_text(encoding='utf-8'))['records']
            assert [p['page'] for p in pages]==list(range(1,u['page_count']+1))
            assert all(f'<!-- original PDF page {i} -->' in body for i in range(1,u['page_count']+1))
            assert u['verification_status']=='acquired-normalized-unsuitable-for-freeze'
        if u['language_status']=='mixed-pl-en-user-approved':
            assert {p['language'] for p in spans}>={'pl','en'}


def test_source_content_and_existing_ingestion_without_embeddings(corpus):
    root,_=corpus
    result=audit(root)
    assert result['unit_count']==24
    assert not result['exact_duplicate_bodies']
    assert len(result['long_documents'])>=6
    assert all(p['blob_verified'] and p['all_assets_present'] for p in result['progit'])
    assert all(not p['unmatched_paragraphs'] and not p['missing_headings'] and p['all_preformatted_lines_preserved'] for p in result['postgresql'])
    assert all(result['chunks'][s]<=3000 for s in result['chunks'])


def test_offline_inventory(corpus):
    root,_=corpus
    result=verify(root)
    assert result['verified'],result['errors']
