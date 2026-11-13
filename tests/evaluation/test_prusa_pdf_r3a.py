"""Representation-review regressions on the actual public R3A excerpts."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
from audit_prusa_r2 import flat


@pytest.fixture(scope='module')
def review():
    root=os.environ.get('LAEW_PRUSA_R3A_ROOT')
    if not root:pytest.skip('Set LAEW_PRUSA_R3A_ROOT to local public representation review')
    path=Path(root)
    return path,json.loads((path/'results.json').read_text(encoding='utf-8'))


def test_r2_equal_count_is_a_measured_identical_partition(review):
    _,data=review
    all_r2=data['full_r2_equality']
    assert sum(m['legacy_chunks'] for m in all_r2)==3980
    assert sum(m['packets'] for m in all_r2)==3318
    assert sum(m['source_headings'] for m in all_r2)==662
    assert all(m['legacy_chunks']==m['packets']+m['source_headings']==m['v2_chunks'] for m in all_r2)
    assert all(m['trimmed_chunk_sequence_identical'] and m['v2_synthetic_characters']==0 for m in all_r2)


def test_only_seven_complete_selected_section_groups_from_six_manuals(review):
    root,data=review
    assert len(data['samples'])==7 and len({s['source_id'] for s in data['samples']})==6
    assert len(list((root/'natural').glob('*.md')))==7
    assert all(s['sections'] and s['pages'] and s['fidelity_checks'] for s in data['samples'])
    assert data['integrity_before']==data['integrity_after']


@pytest.mark.parametrize('sample',['mk3s-menu','xl-sheet','mk4s-calibration','mk4-calibration','mini-sheets','mmu-procedures','mmu-purge-table'])
def test_source_once_without_forced_packet_boundaries_and_no_silent_loss(review,sample):
    root,data=review
    s=next(s for s in data['samples'] if s['sample']==sample)
    text=(root/'natural'/f'{sample}.md').read_text(encoding='utf-8')
    assert '###### [R2 ' not in text and '[Derived repeats]' not in text
    assert hashlib.sha256((root/'natural'/f'{sample}.md').read_bytes()).hexdigest()==s['representations']['natural']['sha256']
    assert not s['strategies_trimmed_sequence_identical']['natural']
    fidelity=json.loads((root/'fidelity'/f'{sample}.json').read_text(encoding='utf-8'))
    assert all(c['source_text_or_cell_retained'] for c in fidelity)
    for mode in ('r2','natural'):
        for strategy in ('legacy','structure-v2'):
            d=s['representations'][mode]['strategies'][strategy]
            assert d['missing_nonwhitespace_source_characters']==d['ambiguous_alignment_chunks']==0
            assert d['max_characters']<=1000 and d['all_dependency_source_pieces_available_in_document']
    assert s['representations']['natural']['derived_repetition_characters']==0


def test_native_table_cell_ranges_match_original_values(review):
    root,data=review
    for sample in ('mini-sheets','mmu-purge-table'):
        text=(root/'natural'/f'{sample}.md').read_text(encoding='utf-8')
        mapping=json.loads((root/'maps'/f'{sample}-natural.json').read_text(encoding='utf-8'))
        tables=[(b,r) for b,r in zip(mapping['source_blocks'],mapping['records']) if b['kind']=='table']
        assert tables
        for b,r in tables:
            for cell in r['cells']:
                source=b['source_rows'][cell['row']][cell['column']] or ''
                own=text[cell['start']:cell['end']]
                assert flat(source).replace('\\','')==flat(own).replace('\\','')


def test_dependency_visibility_is_measured_not_declared_universal(review):
    _,data=review
    menu=next(s for s in data['samples'] if s['sample']=='mk3s-menu')['representations']['natural']['strategies']
    assert menu['legacy']['procedure_chunks_all_dependencies']<menu['legacy']['procedure_chunks_with_dependencies']
    assert menu['structure-v2']['procedure_chunks_all_dependencies']==menu['structure-v2']['procedure_chunks_with_dependencies']
    assert any(d['dependencies_retained']<d['dependency_checks'] for s in data['samples'] for d in s['representations']['natural']['strategies'].values())


def test_all_high_findings_keep_original_priority_and_pending_human_gates(review):
    root,_=review
    policy=json.loads((root/'risk-policy-proposals.json').read_text(encoding='utf-8'))
    high=[r for r in policy['records'] if r['original_severity']=='High']
    assert len(high)==388 and len(policy['records'])==418
    assert all(not r['severity_changed'] and r['disposition'].startswith('pending') for r in policy['records'])
    visual=[r for r in high if r['proposed_gate']=='visual-only-candidate-needs-human-disposition']
    assert len(visual)==43 and all(r['unique_flags']==['substantial-image-visual-review'] for r in visual)
    assert policy['unique_page_flag_counts']['merged-or-ambiguous-table-cells']==16
