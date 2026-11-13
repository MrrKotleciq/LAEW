"""Versioned pilot amendment and sealed draft preparation, before retrieval."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import prepare_real_world_pilot as base

DATE = "2026-11-13"


def seal(out, source, kind, parent=None):
    base.write(out / "dataset-integrity.json", dict(schema_version=1, kind=kind,
        status="content-frozen-agent-draft-provisional", date=DATE, human_domain_review=False,
        independent_validation=False, parent_manifest_sha256=parent, source_manifest_sha256=base.MANIFEST_SHA,
        files=[dict(path=p.name, bytes=p.stat().st_size, sha256=base.digest(p)) for p in sorted(out.iterdir()) if p.is_file()]))
    return dict(output=str(out), sha256=base.digest(out / "dataset-integrity.json"))


def verify_dataset(out, expected=None):
    if expected:
        base.require(base.digest(out / "dataset-integrity.json") == expected, "Dataset manifest anchor mismatch")
    manifest = base.load(out / "dataset-integrity.json")
    base.require({p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()} == {f['path'] for f in manifest['files']} | {'dataset-integrity.json'}, "Dataset file set changed")
    for f in manifest['files']:
        p=base.local(out,f['path'])
        base.require(p.stat().st_size==f['bytes'] and base.digest(p)==f['sha256'], "Dataset file changed: "+f['path'])
    return manifest


def revise_pilot(root, previous, out, amendment):
    base.verify(root, previous, 'a9bd1d0828fd39725a1801916f2584b31810687af2d68fc4b8eb8c4f9ed780cc')
    change=base.load(amendment)
    base.require(set(change['questions'])=={'en','pl','de'},'Three amendment languages required')
    base.require(not out.exists(), 'New pilot path required')
    out.mkdir(parents=True)
    for p in previous.iterdir():
        if p.is_file() and p.name!='pilot-integrity-manifest.json':shutil.copyfile(p,out/p.name)
    families=base.load(previous/'families.json');questions=base.load(previous/'questions.json');labels=base.load(previous/'draft-labels.json')
    f=next(f for f in families if f['id']=='P02')
    f['questions']=change['questions']
    f['target']['assumptions']=change['assumptions']
    statements=change['fact_statements']
    base.require(set(statements)=={fact['id'] for fact in f['facts']},'Unexpected amendment fact IDs')
    for fact in f['facts']:fact['statement']=statements[fact['id']]
    f['warnings_and_conditions']=change['warnings_and_conditions']
    for q in questions:
        if q['family_id']=='P02':q['text']=f['questions'][q['language']];q['origin']='human' if q['language']=='pl' else 'agent';q['wording_provenance']='User supplied PL replacement; agent-authored equivalent EN/DE' if q['language']=='pl' else 'Agent translation of user-supplied PL replacement'
    for label in labels:
        if label['family_id']=='P02':
            label.update(target=f['target'],required_answer_facts=f['facts'],warnings_and_conditions=f['warnings_and_conditions'])
    for q in questions:
        if q['family_id']!='P02':base.require(q==next(x for x in base.load(previous/'questions.json') if x['id']==q['id']),'Unauthorised pilot question change')
    for label in labels:
        if label['family_id']!='P02':base.require(label==next(x for x in base.load(previous/'draft-labels.json') if x['question_id']==label['question_id']),'Unauthorised pilot label change')
    for name,value in [('families.json',families),('questions.json',questions),('draft-labels.json',labels)]:base.write(out/name,value)
    spans={s['id']:s for s in base.load(out/'evidence-spans.json')}
    (out/'review.html').write_text(base.render_review(root,families,spans),encoding='utf-8')
    (out/'blind-second-review.html').write_text(base.render_review(root,families,spans,blind=True),encoding='utf-8')
    base.write(out/'user-naturalness-feedback.json',dict(origin='human',date_recorded=DATE,review_timestamp=None,
        scope='Polish question naturalness only; no technical gold certification or independent label validation',
        decisions={'P01':'Accepted without changes','P03':'Accepted without changes','P04':'Accepted as natural in a conversational context','P02':'User supplied replacement wording'},
        pl_replacement=f['questions']['pl'],en_de_review='Agent equivalence review only',label_status='agent_draft'))
    base.write(out/'provenance.json',dict(date=DATE,origin='agent',status='agent_draft',source_root=str(root),parent=str(previous),parent_manifest_sha256=base.digest(previous/'pilot-integrity-manifest.json'),amendment_sha256=base.digest(amendment),human_feedback='user-naturalness-feedback.json',technical_labels_human_reviewed=False,retrieval_outputs_seen=False))
    (out/'README.md').write_text('# Pilot v4\n\nUser PL naturalness feedback is separate from agent-draft technical labels. P02 is open wording with conditional cleaning and first-layer adjustment; P01/P03/P04 questions and labels are unchanged. This hash freeze authorizes no generation. Never index this package.\n',encoding='utf-8')
    shutil.copyfile(Path(__file__),out/'prepare_real_world_dataset.py')
    return seal(out,root,'pilot-v4',base.digest(previous/'pilot-integrity-manifest.json'))


def extract_span(root, spec, unit):
    spec=copy.deepcopy(spec)
    text=(root/'corpus'/unit['normalized_path']).read_text(encoding='utf-8')
    if 'needle' in spec:
        positions=[m.start() for m in re.finditer(re.escape(spec['needle']),text)]
        i=positions[spec.get('occurrence',0)]
        a=text.rfind('\n\n',0,i)+2;z=text.find('\n\n',i);z=len(text) if z<0 else z
        if unit['family']=='progit':
            m=base.load(root/'corpus'/unit['source_map'])
            rows=[r for r in m['records'] if max(a,r['start']+unit['body_offset'])<min(z,r['end']+unit['body_offset'])]
            spec['source_lines']=[min(r['source_line'] for r in rows),max(r['source_line'] for r in rows)]
        else:spec['paragraph_begins']=text[a:z].lstrip()
    mapping=base.load(root/'corpus'/unit['source_map'])
    record=next((r for r in mapping['records'] if r.get('id')==spec['block_id']),None) if 'block_id' in spec else None
    if record and record.get('derived_segments'):
        # Repaired product tables have neutral, explicitly derived empty headers.
        # Use ONLY the contiguous publisher rows after that header; do not turn
        # the header annotation into technical reference evidence.
        base.require(record['kind']=='table' and all(d['kind']=='derived-neutral-empty-table-header' for d in record['derived_segments']),'Unsupported derived evidence block: '+spec['id'])
        a=max(d['end'] for d in record['derived_segments']);z=record['end'];excerpt=text[a:z]
        page=next(p for p in mapping['pages'] if p['page']==record['page'])
        base.require(a<z and record['cells'] and spec.get('visual_qa_note'),'Table rows need native cells and visual QA')
        result=dict(id=spec['id'],source_id=unit['id'],revision=unit['revision'],commit=unit.get('commit'),normalized_path=unit['normalized_path'],normalized_sha256=unit['normalized_sha256'],original_sha256=unit['original_sha256'],start=a,end=z,text=excerpt,text_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),actual_evidence_language=spec['language'],offset_basis='LF-normalized full-file Unicode [start,end)',location=dict(section=spec['section'],original_path=unit['original_path'],canonical_url=unit['canonical_url'],pdf_page=record['page'],block_id=record['id'],source_line_ids=record['source_lines'],render_path=page['render_path'],render_sha256=page['render_sha256']),qa=dict(origin='agent',status='agent_targeted_qa_passed',human_reviewed=False,method='Visual original-table/native-cell comparison; derived neutral header excluded',observation=spec['visual_qa_note'],original_priority_unchanged=True))
    else:
        try:result=base.make_span(root,spec,unit)
        except ValueError as error:raise ValueError(spec['id']+': '+str(error)) from error
    if spec.get('narrow'):
        excerpt=spec['narrow'];requirement=result['text']
        base.require(requirement.count(excerpt)==1,'Narrow evidence selector must be unique inside QA context')
        offset=requirement.index(excerpt)
        result['qa']['full_context_start']=result['start'];result['qa']['full_context_end']=result['end']
        result['start']+=offset;result['end']=result['start']+len(excerpt);result['text']=excerpt
        result['text_sha256']=hashlib.sha256(excerpt.encode()).hexdigest()
    return result


def prepare_sealed(root, authoring, out, pilot):
    base.verify_corpus(root);verify_dataset(pilot)
    data=base.load(authoring);families=data['families']
    base.require(len(families)==16 and Counter(f['category'] for f in families)==Counter(single_document=5,multi_section=5,multi_document=3,insufficiently_specified=3),'Sealed category quota failed')
    base.require(not out.exists(),'New sealed output required')
    units={u['id']:u for u in base.load(root/'corpus/source-manifest.json')['source_units']}
    spans={s['id']:extract_span(root,s,units[s['source_id']]) for s in data['spans']}
    questions=[];labels=[]
    for f in families:
        base.require(set(f['questions'])=={'en','pl','de'},'Missing language variant')
        for fact in f['facts']:base.require(all(all(s in spans for s in alt) for alt in fact['evidence_alternatives']),'Unknown evidence span')
        for sufficient in f['minimal_sufficient_evidence_sets']:
            base.require(all(any(set(alt)<=set(sufficient) for alt in fact['evidence_alternatives']) for fact in f['facts']),'Insufficient declared evidence set')
            if f['category']=='multi_document':base.require(len({spans[s]['source_id'] for s in sufficient})>=2,'Multi-document set must use complementary sources')
        for lang,question in f['questions'].items():
            qid=f['id']+'-'+lang
            questions.append(dict(id=qid,family_id=f['id'],language=lang,text=question,split='sealed',origin='agent',status='agent_draft'))
            labels.append(dict(question_id=qid,family_id=f['id'],origin='agent',status='agent_draft',human_reviewers=[],target=f['target'],answerability=f['answerability'],positive_evidence_recall_applicable=f['category']!='insufficiently_specified',required_answer_facts=f['facts'],minimal_sufficient_evidence_sets=f['minimal_sufficient_evidence_sets'],warnings_and_conditions=f['warnings_and_conditions'],expected_limitations=f['limitations'],unresolved_review_issues=f['review_issues'],source_freeze_manifest_sha256=base.MANIFEST_SHA))
    pilot_spans=base.load(pilot/'evidence-spans.json')
    intersections=[]
    for s in spans.values():
        for old in pilot_spans:
            if s['source_id']==old['source_id'] and max(s['start'],old['start'])<min(s['end'],old['end']):intersections.append((s['id'],old['id']))
    base.require(not intersections,'Pilot/sealed source overlap: '+str(intersections))
    long_distance=[]
    all_spans={**spans,**{s['id']:s for s in pilot_spans}}
    for f in base.load(pilot/'families.json')+families:
        selected=[all_spans[s] for fact in f['facts'] for alt in fact['evidence_alternatives'] for s in alt if s in all_spans]
        best=0
        for sid in {s['source_id'] for s in selected}:
            trace=base.load(root/f'corpus/chunk-maps/{sid}-legacy.json')['records']
            indices=[r['index'] for s in selected if s['source_id']==sid for r in trace if max(s['start'],r['start'])<min(s['end'],r['end'])]
            if indices:best=max(best,max(indices)-min(indices))
        long_distance.append(dict(family_id=f['id'],legacy_primary_position_distance=best,qualifies=best>=10))
    base.require(sum(x['qualifies'] for x in long_distance)>=6,'Six long-distance families required before retrieval')
    covered={spans[s]['source_id'] for f in families if f['category']!='insufficiently_specified' for fact in f['facts'] for alt in fact['evidence_alternatives'] for s in alt}
    base.require({u['id'] for u in units.values() if u['family']=='prusa'}<=covered,'Six Prusa manuals must have sealed answerable coverage')
    out.mkdir(parents=True)
    for name,value in [('families.json',families),('questions.json',questions),('draft-labels.json',labels),('evidence-spans.json',list(spans.values())),('authoring-plan.json',data)]:base.write(out/name,value)
    (out/'review.html').write_text(base.render_review(root,families,spans),encoding='utf-8')
    (out/'blind-second-review.html').write_text(base.render_review(root,families,spans,blind=True),encoding='utf-8')
    scans=[]
    for unit in units.values():
        t=(root/'corpus'/unit['normalized_path']).read_text(encoding='utf-8')
        scans.append(dict(source_id=unit['id'],sha256=unit['normalized_sha256'],term_counts={term:len(re.findall(re.escape(term),t,re.I)) for term in data['inspection_terms']},relevance='unjudged except proposed spans; absence is not inferred from search alone'))
    base.write(out/'qa.json',dict(origin='agent',human_domain_review=False,independent_agreement=None,source_qa='Original mapped text/native page renders, exact versions, values and conditions; draft scope only',span_count=len(spans),restricted_overlaps=0,pilot_source_overlaps=intersections,long_distance=long_distance,prusa_sealed_coverage=sorted(x for x in covered if x.startswith('prusa')),category_counts=dict(Counter(f['category'] for f in families)),cross_language=data['cross_language_review'],topic_separation=data['topic_separation'],corpus_wide_inspection=scans,retained_uninspected_high=329,review_requirements=data['review_requirements'],retrieval_outputs_seen=False))
    base.write(out/'provenance.json',dict(date=DATE,origin='agent',status='agent_draft',source_manifest_sha256=base.MANIFEST_SHA,source_root=str(root),retrieval_outputs_seen=False,reviewers=[],generator_sha256=base.digest(Path(__file__))))
    shutil.copyfile(Path(__file__),out/'prepare_real_world_dataset.py')
    base.verify_corpus(root)
    return seal(out,root,'sealed-draft-48',data.get('parent_dataset_manifest_sha256'))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['pilot','sealed','verify']);ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--pilot',type=Path);ap.add_argument('--authoring',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--expected-sha')
    a=ap.parse_args()
    if a.mode=='pilot':
        base.require(a.authoring is not None,'External --authoring amendment required')
        result=revise_pilot(a.corpus,a.pilot,a.output,a.authoring)
    elif a.mode=='sealed':result=prepare_sealed(a.corpus,a.authoring,a.output,a.pilot)
    else:base.verify_corpus(a.corpus);verify_dataset(a.output,a.expected_sha);result={'verified':True,'sha256':base.digest(a.output/'dataset-integrity.json')}
    print(json.dumps(result,indent=2))
