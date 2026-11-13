"""Source-span scoring, dataset isolation and native renderer regressions."""
import hashlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

from laew.eval.real_world_retrieval import union,span_present,score_stage,payload_segments,ARMS


def test_union_multispan_whitespace_and_missing_negation():
    texts={'s':'alpha not beta'};span=dict(source_id='s',start=0,end=14)
    assert union([(3,7),(0,4),(9,11)])==[(0,7),(9,11)]
    assert span_present(span,{'s':[(0,5),(6,14)]},texts)
    assert not span_present(span,{'s':[(0,5),(10,14)]},texts)
    assert not span_present(span,{'wrong-version':[(0,14)]},texts)


def test_alternative_sets_do_not_mix_incompatible_procedures():
    spans={s:dict(source_id=s,start=0,end=1) for s in ['a','b','c','d']}
    label=dict(positive_evidence_recall_applicable=True,required_answer_facts=[dict(id='f1',evidence_alternatives=[['a'],['c']]),dict(id='f2',evidence_alternatives=[['b'],['d']])],minimal_sufficient_evidence_sets=[['a','b'],['c','d']])
    result=score_stage(label,spans,{'a':[(0,1)],'d':[(0,1)]},{s:'x' for s in spans},['f2'])
    assert result['fact_recall']==.5 and not result['complete']
    complete=score_stage(label,spans,{'a':[(0,1)],'b':[(0,1)]},{s:'x' for s in spans},['f2'])
    assert complete['complete'] and complete['warning_coverage']==1


def test_unsupported_is_not_vacuous_complete():
    result=score_stage({'positive_evidence_recall_applicable':False},{},{},{})
    assert result['complete'] is None and result['fact_recall'] is None


def test_clipping_cannot_credit_invisible_primary_or_context():
    chunk=SimpleNamespace(text='[Related context]\nwarning\nBODY')
    syn=len(chunk.text)-4
    mapping=dict(start=7,end=11,synthetic_chars=syn,context_spans=[[0,7]])
    assert payload_segments(chunk,mapping,'warningBODY',len('[Related context]\nwar'))==[(0,3)]
    assert payload_segments(chunk,mapping,'warningBODY')==[(0,11)]


def test_arms_are_exact_no_experimental_extra_policy():
    assert ARMS=={'A':('legacy',2,'top2',500),'B':('legacy',10,'ranked_fill',1000),'C':('structure-v2',10,'ranked_fill',1000)}


def test_first_dispatch_replay_stops_before_http_or_answer():
    from laew.eval.real_world_payload_replay import observe
    result=observe('A public technical question','Relevant Global Knowledge (untrusted):\n[manual.pdf]\nDo not energize before connecting.')
    assert result['first_dispatch_context_received'] and result['network_requests']==0 and result['answers_generated']==0


@pytest.fixture(scope='module')
def datasets():
    root=os.environ.get('LAEW_FROZEN_CORPUS_ROOT');pilot=os.environ.get('LAEW_REAL_WORLD_PILOT_V4');sealed=os.environ.get('LAEW_REAL_WORLD_SEALED')
    if not all([root,pilot,sealed]):pytest.skip('Set frozen corpus, pilot v4 and sealed dataset paths')
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
    import prepare_real_world_dataset as d
    return d,Path(root),Path(pilot),Path(sealed)


def test_datasets_frozen_before_retrieval_and_pilot_only_p02_changes(datasets):
    d,root,pilot,sealed=datasets
    d.verify_dataset(pilot,'9060c3027424da26c5c49888cea62d423a7df543242258f8eb0629c58360bcf6')
    d.verify_dataset(sealed,'4f19aba5f77f8012d74bdfdfc7305cdbba330672fa82138c8b108480eec9e437')
    previous=sealed.parent/'stage-2b2-real-world-sealed-20261113-v1'
    assert [x for x in d.base.load(sealed/'questions.json') if x['family_id']!='S09']==[x for x in d.base.load(previous/'questions.json') if x['family_id']!='S09']
    s10=next(f for f in d.base.load(sealed/'families.json') if f['id']=='S10')
    assert all(not any('demand' in s for s in evidence_set) for evidence_set in s10['minimal_sufficient_evidence_sets'])
    assert s10['alternative_valid_workflows'][0]['method']=='on-demand'
    old=pilot.parent/'stage-2b2-real-world-pilot-20261112-v3'
    for name,key in [('questions.json','family_id'),('draft-labels.json','family_id')]:
        assert [x for x in d.base.load(pilot/name) if x[key]!='P02']==[x for x in d.base.load(old/name) if x[key]!='P02']
    feedback=d.base.load(pilot/'user-naturalness-feedback.json')
    assert 'naturalness only' in feedback['scope'] and feedback['label_status']=='agent_draft'


def test_sealed_quotas_exact_spans_and_restricted_exclusions(datasets):
    d,root,pilot,sealed=datasets
    qa=d.base.load(sealed/'qa.json')
    assert qa['category_counts']==dict(single_document=5,multi_section=5,multi_document=3,insufficiently_specified=3)
    assert sum(x['qualifies'] for x in qa['long_distance'])>=6 and len(qa['prusa_sealed_coverage'])==6
    assert not qa['pilot_source_overlaps'] and qa['retained_uninspected_high']==329
    assert len(d.base.load(sealed/'questions.json'))==48
    regs=d.base.load(root/'review/r3d/restricted-regions.json')['regions']
    for s in d.base.load(sealed/'evidence-spans.json'):
        t=(root/'corpus'/s['normalized_path']).read_text(encoding='utf-8')
        assert hashlib.sha256(t[s['start']:s['end']].encode()).hexdigest()==s['text_sha256']
        assert '[Derived' not in s['text']
        for r in regs:
            if r['source_id']==s['source_id']:
                assert all(max(s['start'],p['start'])>=min(s['end'],p['end']) for p in r['component_ranges']+r['related_context_ranges'])


def test_external_pilot_amendment_reproduces_frozen_content(datasets,tmp_path):
    d,root,pilot,sealed=datasets
    amendment=pilot.parent/'stage-2b2-real-world-pilot-20261113-authoring-v4/p02-amendment.json'
    previous=pilot.parent/'stage-2b2-real-world-pilot-20261112-v3'
    output=tmp_path/'reconstructed-pilot'
    d.revise_pilot(root,previous,output,amendment)
    for name in ['families.json','questions.json','draft-labels.json','evidence-spans.json']:
        assert d.base.load(output/name)==d.base.load(pilot/name)
