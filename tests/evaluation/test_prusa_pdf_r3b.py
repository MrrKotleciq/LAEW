"""Regression checks for bounded, source-grounded R3B triage; no stores or models."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
from audit_prusa_r2 import chunk,flat
from triage_prusa_r3b import TABLE_PAGES,NOTE_RUNS,COLUMNS


@pytest.fixture(scope='module')
def triage():
    name=os.environ.get('LAEW_PRUSA_R3B_ROOT')
    if not name:pytest.skip('Set LAEW_PRUSA_R3B_ROOT to the local public triage workspace')
    return Path(name)

def read(root,path):return json.loads((root/path).read_text(encoding='utf-8'))


def test_explicit_bounded_review_and_agent_origin(triage):
    selection=read(triage,'review-selection.json');decisions=read(triage,'inspection-decisions.json')['records']
    assert len(selection['A'])==36 and len(selection['B'])==12 and len(selection['C'])==6
    assert len(decisions)==selection['selected_pages']==60
    assert len({(d['source_id'],d['page']) for d in decisions})==60
    assert all(d['inspection_method'] and d['finding_and_reason'] and d['remaining_uncertainty'] for d in decisions)
    assert all(d['reviewer_origin']=='agent' and not d['independent_human_certification'] and not d['original_priority_changed'] for d in decisions)


@pytest.mark.parametrize('sid,page',TABLE_PAGES)
def test_repaired_native_tables_preserve_all_cells_and_glyphs(triage,sid,page):
    data=read(triage,f'corrected-maps/{sid}-p{page:03d}.json')
    table=next(b for b in data['source_blocks'] if b.get('derived_empty_header'))
    original=''.join(v or '' for row in table['native_source_rows'] for v in row)
    repaired=''.join(v for row in table['source_rows'] for v in row)
    assert Counter(re.sub(r'\s','',original))==Counter(re.sub(r'\s','',repaired))
    assert table['native_cells'] and table['source_glyph_multiset_exact']
    assert table['source_rows'][0]==['','']
    assert all(row[0] for row in table['source_rows'][1:])
    if sid=='prusa-xl-de' and page==81:
        dimensions=next(row for row in table['source_rows'] if 'Abmessungen' in row[0])
        assert all(value in dimensions[1] for value in ['430 mm','62 mm','75,5 mm'])


@pytest.mark.parametrize('sid,page,start,end,cut,header',COLUMNS)
def test_columns_retain_text_without_invented_polarity(triage,sid,page,start,end,cut,header):
    data=read(triage,f'corrected-maps/{sid}-p{page:03d}.json')
    column=next(b for b in data['source_blocks'] if b.get('source_columns'))
    raw=read(Path(os.environ['LAEW_PRUSA_R2_ROOT']),f'geometry/{sid}/{page:03d}.json')
    source=''.join(c['text'] for i in range(start,end+1) for c in raw['lines'][i]['chars'])
    restored=''.join(''.join(c) for c in column['source_columns']).replace('**','')
    assert Counter(re.sub(r'\s','',source))==Counter(re.sub(r'\s','',restored))
    assert column['column_semantics']==('literal-source-headings' if header else 'graphic-polarity-unavailable')
    if not header:assert 'graphic marker meaning unavailable in text' in column['text']


@pytest.mark.parametrize('sid,page,start,end',NOTE_RUNS)
def test_complete_callout_includes_original_tail_once(triage,sid,page,start,end):
    data=read(triage,f'corrected-maps/{sid}-p{page:03d}.json')
    raw=read(Path(os.environ['LAEW_PRUSA_R2_ROOT']),f'geometry/{sid}/{page:03d}.json')
    note=next(b for b in data['source_blocks'] if b['id'].endswith(f':r3b-note-{start}'))
    assert note['source_lines']==list(range(start,end+1))
    assert flat(raw['lines'][end]['text']) in flat(note['text'])
    assert sum(end in b['source_lines'] for b in data['source_blocks'])==1


def test_all_corrected_excerpts_preserve_line_ownership_and_record_hashes(triage):
    repairs=read(triage,'experimental-corrections.json')
    assert len(repairs['pages'])==20 and len(repairs['changes'])==22
    for item in repairs['pages']:
        assert hashlib.sha256((triage/item['path']).read_bytes()).hexdigest()==item['sha256']
        current=read(triage,f'corrected-maps/{item["source_id"]}-p{item["page"]:03d}.json')
        old=read(Path(os.environ['LAEW_PRUSA_R2_ROOT']),f'structured/{item["source_id"]}/{item["page"]:03d}.json')
        assert Counter(i for b in current['source_blocks'] for i in b['source_lines'])==Counter(i for b in old['blocks'] for i in b['source_lines'])


def test_priorities_and_uninspected_cases_are_never_automatically_cleared(triage):
    risks=read(triage,'outstanding-risk-register.json')
    counts=Counter(r['original_severity'] for r in risks)
    assert {level:counts[level] for level in ('Critical','High','Medium','Low')}=={'Critical':0,'High':388,'Medium':10,'Low':20}
    assert sum(r['original_severity']=='High' and not r['r3b_inspected'] for r in risks)==329
    assert sum(r['original_severity']=='Medium' and not r['r3b_inspected'] for r in risks)==9
    assert sum(r['original_severity']=='Low' and not r['r3b_inspected'] for r in risks)==20
    assert all(not r['priority_changed'] and not r['human_certified'] and r['admission_status']=='not-admitted' for r in risks)
    assert all(r['r3b_outcome'] is None for r in risks if not r['r3b_inspected'])


def test_known_visual_safety_gaps_remain_blocked(triage):
    decisions={(d['source_id'],d['page']):d for d in read(triage,'inspection-decisions.json')['records']}
    for key in [('prusa-xl-de',81),('prusa-mmu3-en',6),('prusa-mk4-de',33),('prusa-xl-de',35),('prusa-mk4s-en',19),('prusa-mk4-de',22)]:
        assert decisions[key]['blocks_unqualified_text_only_use']
        assert decisions[key]['human_review_required']
    assert sum(d['blocks_unqualified_text_only_use'] for d in decisions.values())==9


@pytest.mark.parametrize('sample',['mk3s-menu','xl-sheet','mk4s-calibration','mk4-calibration','mini-sheets','mmu-procedures'])
def test_procedures_remain_source_once_with_real_chunker_differences(triage,sample):
    path=triage/'procedure-excerpts'/f'{sample}.md';text=path.read_text(encoding='utf-8')
    sidecar=read(triage,f'procedure-sidecars/{sample}.json')
    assert len(set(sidecar['source_blocks_once']))==len(sidecar['source_blocks_once'])
    assert len(sidecar['mapping'])==len(sidecar['source_blocks_once'])
    assert '[Derived repeats]' not in text and '###### [R2 ' not in text
    legacy=chunk(path,text,'legacy');v2=chunk(path,text,'structure-v2')
    assert all(c.embedding is None and len(c.text)<=1000 for c in legacy+v2)
    assert ''.join(text[c.metadata['start_offset']:c.metadata['end_offset']] for c in v2)==text
    assert [c.text.strip() for c in legacy]!=[c.text.strip() for c in v2]


def test_forecast_is_explicitly_uncertain_and_not_full_corpus_output(triage):
    estimate=read(triage,'resource-estimate.json')
    assert len(estimate['paired_page_samples'])==6
    assert 'not measured uncertainty' in estimate['limitation']
    assert len(list((triage/'procedure-excerpts').glob('*.md')))==6
    assert not (triage/'candidates').exists()


def test_availability_markers_preserve_all_original_text_and_do_not_quarantine_neighboring_sections(triage):
    availability=read(triage,'availability-register.json')
    assert len(availability)==9
    for region in availability:
        sid,p=region['source_id'],region['page']
        corrected=triage/'corrected-excerpts'/f'{sid}-p{p:03d}.md'
        base=corrected if corrected.exists() else triage/'page-excerpts'/f'{sid}-p{p:03d}.md'
        marked=(triage/region['excerpt_path']).read_text(encoding='utf-8')
        unmarked=re.sub(r'\[Derived text-only availability limitation:[^\]]+\]\n\n','',marked)
        assert unmarked==base.read_text(encoding='utf-8')
        assert region['original_text_retained'] and region['source_block_ids']
        if (sid,p) in [('prusa-mk4-de',33),('prusa-xl-de',35)]:
            original=read(Path(os.environ['LAEW_PRUSA_R2_ROOT']),f'structured/{sid}/{p:03d}.json')
            chosen=[b for b in original['blocks'] if b['id'] in region['source_block_ids']]
            assert all('Werkseinstellung' in b['scope'] for b in chosen)
