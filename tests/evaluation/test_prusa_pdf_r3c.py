"""Full R3C source/attribution regressions; no indexing, inference or admission."""
from collections import Counter
import hashlib
import os
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
from regenerate_prusa_r3c import load,patch_identity,WAL_COMMIT
from audit_prusa_r3c import actual_chunks,trimmed_intervals

SIDS=['prusa-mk4s-en','prusa-mmu3-en','prusa-mk4-de','prusa-xl-de','prusa-mini-pl','prusa-mk3s-pl']


@pytest.fixture(scope='module')
def corpus():
    value=os.environ.get('LAEW_PRUSA_R3C_ROOT')
    if not value:pytest.skip('Set LAEW_PRUSA_R3C_ROOT to the local full candidate workspace')
    root=Path(value)
    return root,load(root/'source-manifest.json')


def test_all_24_sources_originals_and_18_unchanged_markdown_files(corpus):
    root,manifest=corpus;accepted=Path(os.environ['LAEW_PUBLIC_CORPUS_ROOT']);baseline={u['id']:u for u in load(accepted/'source-manifest.json')['source_units']}
    assert len(manifest['source_units'])==24 and {u['id'] for u in manifest['source_units']}==set(baseline)
    for u in manifest['source_units']:
        assert hashlib.sha256((root/u['original_path']).read_bytes()).hexdigest()==baseline[u['id']]['original_sha256']
        assert hashlib.sha256((root/u['normalized_path']).read_bytes()).hexdigest()==u['normalized_sha256']
        if u['family']!='prusa':
            assert (root/u['normalized_path']).read_bytes()==(accepted/u['normalized_path']).read_bytes()
            assert u.get('commit')==baseline[u['id']].get('commit') and u['language_status']==baseline[u['id']]['language_status']
    assert next(u['commit'] for u in manifest['source_units'] if u['id']=='postgresql-17-runtime-config-wal')==WAL_COMMIT


@pytest.mark.parametrize('sid',SIDS)
def test_complete_maps_pages_and_explicit_derived_provenance(corpus,sid):
    root,manifest=corpus;u=next(u for u in manifest['source_units'] if u['id']==sid);mapping=load(root/u['source_map']);text=(root/u['normalized_path']).read_text(encoding='utf-8')
    assert len(mapping['pages'])==u['page_count']
    assert [p['page'] for p in mapping['pages']]==list(range(1,u['page_count']+1))
    records=mapping['records'];assert records[0]['start']==mapping['body_offset'] and records[-1]['end']==len(text)
    assert all(a['end']==b['start'] for a,b in zip(records,records[1:]))
    assert len({r['id'] for r in records})==len(records)
    assert '###### [R2 ' not in text and '[Derived repeats]' not in text
    for record in records:
        for d in record.get('derived_segments',[]):assert record['start']<=d['start']<d['end']<=record['end']
        if record['kind']=='derived-availability':assert record['text_origin']=='derived-availability' and not record['contains_publisher_text']
    for p in mapping['pages']:
        assert (root/p['render_path']).is_file()
        assert hashlib.sha256((root/p['render_path']).read_bytes()).hexdigest()==p['render_sha256']


def test_hash_gates_reject_wrong_source_identities(corpus):
    root,manifest=corpus;sid='prusa-xl-de';u=next(u for u in manifest['source_units'] if u['id']==sid)
    r3b=Path(os.environ['LAEW_PRUSA_R3B_ROOT']);patch=load(r3b/'corrected-maps/prusa-xl-de-p081.json')
    patch_identity(u,u['original_sha256'],patch['source_structured_sha256'],patch)
    with pytest.raises(ValueError,match='PDF identity'):patch_identity(u,'0'*64,patch['source_structured_sha256'],patch)
    with pytest.raises(ValueError,match='structured source identity'):patch_identity(u,u['original_sha256'],'0'*64,patch)


def test_exactly_22_repairs_and_original_page_ownership(corpus):
    root,manifest=corpus;repairs=load(root/'applied-repairs.json');r2=Path(os.environ['LAEW_PRUSA_R2_ROOT'])
    assert len(repairs['repair_operations'])==22 and len(repairs['pages'])==20
    for repair in repairs['repair_operations']:assert repair['applied'] and repair['source_pdf_sha256'] and repair['expected_structured_sha256']
    total=0
    for sid in SIDS:
        m=load(root/f'maps/{sid}.json');blocks={b['id']:b for b in m['source_blocks']}
        for p in m['pages']:
            old=load(r2/'structured'/sid/f'{p["page"]:03d}.json')
            before=Counter(i for b in old['blocks'] for i in b['source_lines'])
            after=Counter(i for bid in p['source_block_ids'] for i in blocks[bid]['source_lines'])
            assert before==after and all(n==1 for n in after.values());total+=1
    assert total==418


def test_all_418_page_checks_are_structural_not_semantic_admission(corpus):
    root,_=corpus;audit=load(root/'structural-audit-418.json')
    assert audit['pages']==audit['passed']==418 and audit['failed_pages']==0 and not audit['failed_checks']
    assert audit['checks']['cells']>=235 and audit['checks']['technical_tokens']>=6000
    assert all(not p['semantic_certification'] for p in audit['records'])


def test_nine_precise_availability_limits_and_fifteen_open_human_gates(corpus):
    root,_=corpus;r3b=Path(os.environ['LAEW_PRUSA_R3B_ROOT'])
    available=load(root/'availability-register.json');original=load(r3b/'availability-register.json')
    assert {(r['source_id'],r['page']) for r in available}=={(r['source_id'],r['page']) for r in original} and len(available)==9
    for region in available:
        mapping=load(root/f'maps/{region["source_id"]}.json');text=(root/region['normalized_path']).read_text(encoding='utf-8')
        old=next(r for r in original if (r['source_id'],r['page'])==(region['source_id'],region['page']))
        ar=next(r for r in old['mapping'] if r['id'].endswith(':r3b-availability'));old_text=(r3b/old['excerpt_path']).read_text(encoding='utf-8')[ar['start']:ar['end']]
        assert text[region['start']:region['end']]==old_text
        assert [r['id'] for r in region['source_ranges']]==region['source_block_ids']
        assert all(r['page']==region['page'] for r in region['source_ranges'])
    gates=load(root/'mandatory-human-review-gates.json');old_gates=load(r3b/'triage-results.json')['mandatory_human_review_pages']
    assert {(g['source_id'],g['page']) for g in gates}=={(g['source_id'],g['page']) for g in old_gates} and len(gates)==15
    assert all(g['source_ranges'] and g['status']=='mandatory-human-review-pending' and not g['human_certified'] for g in gates)


def test_complete_risk_queue_priorities_and_329_uninspected_high_are_preserved(corpus):
    root,_=corpus;risks=load(root/'unresolved-risk-register.json');inherited=load(root/'inherited-r3b/outstanding-risk-register.json')
    assert len(risks)==418
    assert [(p['source_id'],p['page'],p['original_severity'],p['r3b_inspected']) for p in risks]==[(p['source_id'],p['page'],p['original_severity'],p['r3b_inspected']) for p in inherited]
    assert sum(p['original_severity']=='High' and not p['r3b_inspected'] for p in risks)==329
    assert Counter(p['original_severity'] for p in risks)==Counter(High=388,Medium=10,Low=20)
    assert all(not p['priority_changed'] and not p['semantic_certification'] and p['admission_status']=='not-admitted' for p in risks)


@pytest.mark.parametrize('sid',SIDS)
def test_actual_unchanged_loader_partitions_and_differing_payloads(corpus,sid):
    root,manifest=corpus;u=next(u for u in manifest['source_units'] if u['id']==sid);path=root/u['normalized_path'];text=path.read_text(encoding='utf-8')
    legacy,offset=actual_chunks(path,text,'legacy');v2,offset2=actual_chunks(path,text,'structure-v2')
    assert offset==offset2==u['body_offset']
    assert all(0<len(c['text'])<=1000 for c in legacy+v2)
    assert ''.join(text[c['start']:c['end']] for c in v2)==text[offset:]
    assert all(text[c['start']:c['end']]==c['text'] for c in legacy)
    assert all(text[c['start']:c['end']]==c['text'][c['synthetic_chars']:] for c in v2)
    assert trimmed_intervals(legacy,text)!=trimmed_intervals(v2,text)
    assert [c['text'].strip() for c in legacy]!=[c['text'].strip() for c in v2]


def test_all_24_metrics_have_attribution_distributions_and_no_reference_failures(corpus):
    root,_=corpus;metrics=load(root/'chunking-comparison.json')
    assert len(metrics['units'])==24 and not metrics['local_reference_failures']
    for u in metrics['units']:
        for strategy in ('legacy','structure-v2'):
            m=u['chunking'][strategy]
            assert m['source_attribution'] and not m['missing_nonwhitespace_ranges'] and m['sizes']['max']<=1000
            cm=load(root/f'chunk-maps/{u["source_id"]}-{strategy}.json')
            assert len(cm['records'])==m['chunks'] and cm['normalized_sha256']==u['normalized_sha256']
    assert metrics['no_forced_identical_prusa_payloads']


def test_natural_native_lists_and_untranslated_publisher_text(corpus):
    root,_=corpus;en=(root/'normalized/prusa-mk4s-en.md').read_text(encoding='utf-8');pl=(root/'normalized/prusa-mk3s-pl.md').read_text(encoding='utf-8')
    assert '- Test of heatsink fan and print fan' in en
    assert '- **Kabel USB**' in pl
    assert 'Read chapter about our new' in pl
    for sid in SIDS:
        m=load(root/f'maps/{sid}.json')
        assert all(not c['technical_text_changed'] for c in m['representation_changes'])


def test_source_images_all_preserved_and_no_invented_visual_descriptions(corpus):
    root,_=corpus;objects=load(root/'image-object-register.json')
    assert objects and len(list((root/'assets/prusa-pages').glob('*/*.png')))==418
    assert all((root/i['source_pdf_path']).is_file() and (root/i['render_path']).is_file() for i in objects)
    assert all(i['visual_meaning']=='unavailable-or-unreviewed; no inferred description' for i in objects)


def test_six_reviewed_scopes_rebased_without_delivering_sidecars_to_llm(corpus):
    root,_=corpus;groups=load(root/'warning-applicability-reviewed.json')
    assert len(groups)==6
    for group in groups:
        m=load(root/f'maps/{group["source_id"]}.json');records={r['id']:r for r in m['records']}
        assert not group['sidecar_delivery_to_llm'] and not group['independent_human_certification']
        assert all(r['start']==records[r['id']]['start'] and r['end']==records[r['id']]['end'] for r in group['source_ranges'])
