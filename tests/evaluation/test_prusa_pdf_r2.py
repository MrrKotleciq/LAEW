"""R2 regressions on actual public source candidates; no stores or models."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
from prusa_pdf_r2 import packetize,DependencyCapacityError
from audit_prusa_r2 import chunk


@pytest.fixture(scope='module')
def r2():
    value=os.environ.get('LAEW_PRUSA_R2_ROOT')
    if not value:pytest.skip('Set LAEW_PRUSA_R2_ROOT to versioned public R2 workspace')
    return Path(value)


def load(root,path):
    return json.loads((root/path).read_text(encoding='utf-8'))


def test_six_complete_candidates_and_418_source_pages(r2):
    results=load(r2,'candidate-results.json');audit=load(r2,'automated-audit.json')
    assert len(results)==6 and sum(r['pages'] for r in results)==418
    assert len(audit['page_records'])==418
    for source in results:
        path=r2/source['candidate_path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
        assert len(list((r2/'structured'/source['id']).glob('*.json')))==source['pages']
        assert len(list((r2/'page-renders'/source['id']).glob('*.png')))==source['pages']
    assert all(not p['source_lines_missing'] and not p['duplicate_primary_lines'] and not p['glyph_lines_missing'] for p in audit['page_records'])
    assert all(not p['table_cells_missing'] and not p['numeric_values_missing'] and not p['primary_partition_errors'] for p in audit['page_records'])


@pytest.mark.parametrize('strategy',['legacy','structure-v2'])
@pytest.mark.parametrize('sid',['prusa-mk3s-pl','prusa-xl-de','prusa-mk4s-en','prusa-mk4-de','prusa-mini-pl','prusa-mmu3-en'])
def test_all_materialized_dependencies_survive_actual_unchanged_chunkers(r2,sid,strategy):
    mapping=load(r2,f'maps/{sid}.json');path=r2/'candidates'/f'{sid}.md';text=path.read_text(encoding='utf-8')
    chunks=chunk(path,text,strategy)
    nodes={b['id']:b for file in (r2/'structured'/sid).glob('*.json') for b in load(r2,file.relative_to(r2))['blocks']}
    nodes.update({d['id']:d for d in mapping['derived_dependencies']})
    assert all(c.embedding is None and len(c.text)<=1000 for c in chunks)
    indexed={c.text.splitlines()[0]:c.text for c in chunks}
    for packet in mapping['packets']:
        own=indexed[packet['text'].splitlines()[0]]
        assert all(nodes[d]['text'] in own for d in packet['dependencies'])
    if strategy=='structure-v2':
        assert ''.join(text[c.metadata['start_offset']:c.metadata['end_offset']] for c in chunks)==text


def test_menu_cross_page_ancestry_and_general_note(r2):
    p35=load(r2,'structured/prusa-mk3s-pl/035.json');p36=load(r2,'structured/prusa-mk3s-pl/036.json')
    menu35=next(b for b in p35['blocks'] if b['kind']=='menu')
    menu36=next(b for b in p36['blocks'] if b['kind']=='menu')
    assert len(menu35['rows'])==44
    assert menu36['rows'][0]['path'].startswith('Ustawienia > Ustawienia HW > Sr. dyszy')
    note=next(b for b in p35['blocks'] if b['kind']=='icon-note')
    mapping=load(r2,'maps/prusa-mk3s-pl.json')
    assert all(note['id'] in p['dependencies'] for p in mapping['packets'] if p['block_id'] in {menu35['id'],menu36['id']})


def test_xl_local_and_cross_page_warnings_and_inline_conditions(r2):
    mapping=load(r2,'maps/prusa-xl-de.json');p23=load(r2,'structured/prusa-xl-de/023.json');p24=load(r2,'structured/prusa-xl-de/024.json')
    warnings={b['id'] for p in (p23,p24) for b in p['blocks'] if b['kind']=='warning'}
    assert len(warnings)==3
    condition=next(d for d in mapping['derived_dependencies'] if d['kind']=='source-condition' and not d.get('condition_role'))
    fingers=next(d for d in mapping['derived_dependencies'] if d.get('condition_role')=='finger-clearance')
    assert condition['text'].startswith('Bevor Sie') and 'Heizbett!' in condition['text']
    for packet in mapping['packets']:
        if packet['page'] in (23,24) and packet['kind'] in ('paragraph','step'):
            assert warnings<=set(packet['dependencies'])
            assert condition['id'] in packet['dependencies']
        if packet['block_id']==fingers['origin_block']:assert fingers['id'] in packet['dependencies']


@pytest.mark.parametrize('sid,source_page,target_page',[('prusa-mk4s-en',18,19),('prusa-mk4-de',21,22)])
def test_calibration_prerequisites_continue_to_next_page_without_scope_leak(r2,sid,source_page,target_page):
    mapping=load(r2,f'maps/{sid}.json')
    source=load(r2,f'structured/{sid}/{source_page:03d}.json')
    target=load(r2,f'structured/{sid}/{target_page:03d}.json')
    bed=next(b for b in source['blocks'] if b['kind']=='warning' and ('must be installed' in b['text'] or 'Druckblech muss' in b['text']))
    local=next(b for b in target['blocks'] if b['kind']=='warning')
    filament=next(d for d in mapping['derived_dependencies'] if d.get('condition_role')=='filament-length')
    assert '5 cm' in filament['text']
    for packet in mapping['packets']:
        if packet['page']==target_page and packet['kind'] in ('paragraph','step'):
            assert {bed['id'],local['id'],filament['id']}<=set(packet['dependencies'])
    relations=load(r2,'dependency-relations.json')
    assert all(bed['id'] not in r['dependencies'] for r in relations if r['source_id']==sid and (r['scope'] or '').startswith('4.5'))


def test_table_identity_survives_cell_fragmentation(r2):
    mapping=load(r2,'maps/prusa-mini-pl.json')
    table_packets=[p for p in mapping['packets'] if p['page']==44 and p['kind']=='table']
    assert table_packets
    contexts={d['id']:d for d in mapping['derived_dependencies'] if d['kind']=='table-context'}
    for packet in table_packets:
        component=next(c for c in mapping['components'] if c['id']==packet['component_id'])
        if component['context']:
            assert component['context'] in packet['dependencies']
            assert contexts[component['context']]['text'] in packet['text']


def test_unknown_scope_and_warranty_not_broadcast(r2):
    relations=load(r2,'dependency-relations.json')
    for sid in ['prusa-mini-pl','prusa-xl-de']:
        mapping=load(r2,f'maps/{sid}.json')
        excluded={r['id'] for r in relations if r['source_id']==sid and r['policy'] in ('warranty-primary-only','figure-context-only','unresolved-no-broadcast')}
        assert all(not(excluded&set(p['dependencies'])) for p in mapping['packets'])


def test_capacity_guard_never_truncates_required_source_text(r2):
    p23=load(r2,'structured/prusa-xl-de/023.json')
    note=next(b for b in p23['blocks'] if b['kind']=='warning')
    with pytest.raises(DependencyCapacityError):
        packetize(note['text'],[note],source_id='guard-test',scope='4.3',limit=50)


def test_r1_glyphs_retained_and_unresolved_risks_not_certified(r2):
    r1=Path(os.environ['LAEW_PRUSA_R1_ROOT'])
    for sid,page in [('prusa-mk3s-pl',35),('prusa-xl-de',23),('prusa-mini-pl',31),('prusa-mmu3-en',22)]:
        original=load(r1,f'objects/{sid}-page-{page}.json');actual=load(r2,f'geometry/{sid}/{page:03d}.json')
        assert [[(c['text'],c['x0'],c['top']) for c in l['chars']] for l in original['lines']]==[[(c['text'],c['x0'],c['top']) for c in l['chars']] for l in actual['lines']]
    audit=load(r2,'automated-audit.json')
    assert audit['pages']==418 and audit['severity_counts']['High']>0
    assert all(p['inspection_outcome']=='Requires manual review' for p in audit['page_records'])
    assert any('merged-or-ambiguous-table-cells' in f['reason'] for p in audit['page_records'] for f in p['flags'])


@pytest.mark.parametrize('sid,page',[('prusa-mk4s-en',42),('prusa-mk4-de',43),('prusa-xl-de',46)])
def test_r1_fourteen_item_legends_remain_in_order(r2,sid,page):
    data=load(r2,f'structured/{sid}/{page:03d}.json')
    steps=[b for b in data['blocks'] if b['kind']=='step']
    assert [int(b['text'].split('.')[0]) for b in steps]==list(range(1,15))
    assert any(b['kind']=='figure' and b['visual_verification_required'] for b in data['blocks'])


def test_original_blank_page_has_no_invented_source_content(r2):
    assert not load(r2,'structured/prusa-xl-de/007.json')['blocks']


def test_candidate_figures_resolve_to_original_page_renders(r2):
    import re
    for source in load(r2,'candidate-results.json'):
        path=r2/source['candidate_path']
        links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8'))
        assert links
        assert all((path.parent/link).resolve().is_file() for link in links)
