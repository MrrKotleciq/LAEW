"""R1 regressions against real, opt-in public PDF samples; no models or indexes."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
from prusa_pdf_remediation import SAMPLES,convert_page,menu_rows
from check_prusa_remediation import chunks_for
from laew.rag.markdown_chunker import structure_chunks


@pytest.fixture(scope='module')
def r1():
    value=os.environ.get('LAEW_PRUSA_R1_ROOT')
    if not value:pytest.skip('Set LAEW_PRUSA_R1_ROOT to the external R1 artifacts')
    return Path(value)


def read_case(root,sid,page):
    key=f'{sid}-page-{page}'
    data=json.loads((root/'objects'/f'{key}.json').read_text(encoding='utf-8'))
    maps=json.loads((root/'maps'/f'{key}.json').read_text(encoding='utf-8'))
    return data,maps,(root/'samples'/f'{key}.md').read_text(encoding='utf-8')


def test_three_level_menu_and_source_conditions(r1):
    data,maps,text=read_case(r1,'prusa-mk3s-pl',35)
    rows=next(b['rows'] for b in maps['blocks'] if b['kind']=='menu')
    assert max(r['depth'] for r in rows)==2
    paths={r['path'] for r in rows}
    assert 'Ustawienia > Temperatura > Dysza' in paths
    assert 'Grzanie > PLA - 215/60' in paths
    assert any('tylko podczas procesu drukowania' in p and p.endswith(' > Dysza') for p in paths)
    for strategy in ('legacy','structure-v2'):
        chunks=chunks_for(r1/'samples/prusa-mk3s-pl-page-35.md',text,strategy)
        assert all(any(path in c.text for c in chunks) for path in paths)


def test_two_red_warnings_keep_source_scope_and_graphic_dependency(r1):
    _,maps,text=read_case(r1,'prusa-xl-de',23)
    warnings=[b for b in maps['blocks'] if b['kind']=='warning']
    assert len(warnings)==2
    assert all(b['scope'].startswith('4.3.') and b['marker']=='!' and b['box_color']=='red' for b in warnings)
    subheading=next(b for b in maps['blocks'] if b['kind']=='heading' and not b['numbered'])
    assert all(b['end']<subheading['start'] for b in warnings)
    assert any(b['kind']=='paragraph' and b.get('visual_verification_required') for b in maps['blocks'])
    assert 'Visual verification required' in text


def test_mmu_step_number_reset_and_final_note_scope(r1):
    _,maps,_=read_case(r1,'prusa-mmu3-en',22)
    steps=[b for b in maps['blocks'] if b['kind']=='step']
    assert [int(re.match(r'\d+',b['text'])[0]) for b in steps]==list(range(1,7))*2
    assert all(b['scope'].startswith('2.5.') for b in steps[:6])
    assert all(b['scope'].startswith('2.6.') for b in steps[6:])
    note=next(b for b in maps['blocks'] if b['kind']=='information')
    assert note['marker']=='i' and note['scope'].startswith('2.6.')
    assert note['start']>=steps[-1]['end']


@pytest.mark.parametrize('sid,page,count',[('prusa-mk4s-en',42,14),('prusa-mk4-de',43,14),('prusa-xl-de',46,14),('prusa-mini-pl',31,12)])
def test_existing_legends_preserved_without_transcribing_raster_pixels(r1,sid,page,count):
    _,maps,text=read_case(r1,sid,page)
    steps=[b for b in maps['blocks'] if b['kind']=='step']
    assert [int(re.match(r'\d+',b['text'])[0]) for b in steps]==list(range(1,count+1))
    assert any(b['kind']=='figure' and b['visual_verification_required'] for b in maps['blocks'])
    assert 'Visual verification required' in text


def test_short_numeric_table_columns_and_source_unit(r1):
    _,maps,text=read_case(r1,'prusa-mmu3-en',40)
    table=next(b for b in maps['blocks'] if b['kind']=='table')
    assert table['source_rows'][0]==['Color','Unloaded','Loaded']
    assert ['PVA/BVOH','120','100'] in table['source_rows']
    assert '| White | 70 | 100 |' in text and '70 mm3' in text
    assert any(b.kind=='table' for b in structure_chunks(text,1000))


def test_long_table_keeps_product_and_risk_column_separate(r1):
    _,maps,text=read_case(r1,'prusa-mini-pl',44)
    table=next(b for b in maps['blocks'] if b['kind']=='table')
    assert table['render_kind']=='source-labelled-cells' and table['header_verified']
    assert '#### Teksturowana płyta z powierzchnią proszkową / Ryzyka i zagrożenia:' in text
    assert '90%+' in text and '98A' in text
    callouts=[b for b in maps['blocks'] if b['kind'] in ('warning','information')]
    assert [b['kind'] for b in callouts]==['warning','warning','information','information']
    assert all(b['box_color']=='orange' for b in callouts)


@pytest.mark.parametrize('sid,page',SAMPLES)
def test_sample_replay_is_deterministic_and_parser_source_spans_are_exact(r1,sid,page):
    data,maps,text=read_case(r1,sid,page)
    replay,blocks=convert_page(data,[])
    assert replay==text
    assigned=[line for b in blocks for line in b['source_lines']]
    assert len(assigned)==len(set(assigned))
    chunks=chunks_for(r1/'samples'/f'{sid}-page-{page}.md',text,'structure-v2')
    assert ''.join(text[c.metadata['start_offset']:c.metadata['end_offset']] for c in chunks)==text
    assert all(c.embedding is None and len(c.text)<=1000 for c in chunks)


def test_all_418_pages_screened_without_full_conversion(r1):
    audit=json.loads((r1/'structural-audit-418.json').read_text(encoding='utf-8'))
    assert audit['pages']==len(audit['records'])==418
    expected={'prusa-mk4s-en':66,'prusa-mmu3-en':56,'prusa-mk4-de':69,'prusa-xl-de':85,'prusa-mini-pl':58,'prusa-mk3s-pl':84}
    for sid,count in expected.items():
        assert [r['page'] for r in audit['records'] if r['id']==sid]==list(range(1,count+1))
    assert audit['blank_pages']==[{'id':'prusa-xl-de','page':7}]
    assert len(list((r1/'samples').glob('*.md')))==10
    assert any('merged-or-ambiguous-table-cells' in r['flags'] for r in audit['records'])


def test_source_fidelity_and_context_loss_are_not_hidden(r1):
    checks=json.loads((r1/'chunk-and-fidelity-checks.json').read_text(encoding='utf-8'))
    assert checks['all_non_table_source_lines_preserved'] and checks['all_table_cells_preserved']
    assert all(not stats['menu_paths_missing_in_single_chunk'] and not stats['callouts_split_across_chunks'] for r in checks['records'] for stats in r['strategies'].values())
    xl=next(r for r in checks['records'] if r['id']=='prusa-xl-de' and r['page']==23)
    assert xl['strategies']['legacy']['chunks_without_complete_prior_warnings']>0
    assert xl['strategies']['structure-v2']['chunks_without_complete_prior_warnings']>0


def test_accepted_manifest_and_wal_pin_unchanged(r1):
    root_value=os.environ.get('LAEW_PUBLIC_CORPUS_ROOT')
    assert root_value,'Explicit public corpus path is required'
    corpus=Path(root_value)
    guard=json.loads((r1/'baseline-guard.json').read_text(encoding='utf-8'))
    for name,digest in guard['anchors'].items():
        assert hashlib.sha256((corpus/name).read_bytes()).hexdigest()==digest
        assert (r1/'baseline-snapshot'/name).read_bytes()==(corpus/name).read_bytes()
    assert guard['wal_commit']=='220b5263dbb71bbe2966c6d47c0c456c14ed4e48'
