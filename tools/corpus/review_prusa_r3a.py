"""R3A representation experiment on seven source-selected excerpts; no retrieval."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from audit_prusa_r2 import chunk,flat
from finalize_prusa_r2 import verify

R2_SHA='3fc630e9ca60a06223da8ec8198b13f7b3d51c98193271bab61007e2198ce9fb'
SAMPLES=[
    ('mk3s-menu','prusa-mk3s-pl',('7.2.9',)),
    ('xl-sheet','prusa-xl-de',('4.3',)),
    ('mk4s-calibration','prusa-mk4s-en',('4.3','4.4')),
    ('mk4-calibration','prusa-mk4-de',('4.3','4.4')),
    ('mini-sheets','prusa-mini-pl',('9.1',)),
    ('mmu-procedures','prusa-mmu3-en',('2.5','2.6')),
    ('mmu-purge-table','prusa-mmu3-en',('6.2.2',)),
]


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def number(b):
    m=re.match(r'\d+(?:\.\d+)*',b.get('scope') or '')
    return m[0] if m else None


def natural(blocks):
    """Keep source headings/prose once; no chunk-size-dependent formatting rules."""
    pieces=[];records=[];offset=0
    for b in blocks:
        start=offset;source_start=start;cells=[]
        if b['kind']=='menu':
            text='\n'.join('    '*row['depth']+'- '+row['label'] for row in b['rows'])
        elif b['kind']=='table':
            # Retain the native matrix. Only source-verified headers get a Markdown separator.
            rows=b['source_rows'];lines=[];cursor=start
            for i,row in enumerate(rows):
                line='| ';cursor+=2
                for j,value in enumerate(row):
                    source=value or '';value=source.replace('\\','\\\\').replace('|','\\|').replace('\n','<br>')
                    cells.append(dict(row=i,column=j,start=cursor,end=cursor+len(value),source_sha256=hashlib.sha256(source.encode()).hexdigest()))
                    line+=value+' | ';cursor+=len(value)+3
                lines.append(line.rstrip());cursor-=1;cursor+=1
                if i==0 and b['header_verified']:
                    separator='| '+' | '.join('---' for _ in row)+' |'
                    lines.append(separator);cursor+=len(separator)+1
            text='\n'.join(lines)
        elif b['kind']=='figure':
            text=f'[Visual information unavailable in text; original PDF page {b["page"]}, figure {b.get("image_index","unknown")}.]'
        elif b['kind'] in ('warning','information','icon-note','callout'):
            text='> '+b['text']
            source_start+=2
        else:text=b['text']
        text+='\n\n';pieces.append(text);offset+=len(text)
        records.append(dict(id=b['id'],page=b['page'],kind=b['kind'],scope=b['scope'],source_lines=b['source_lines'],
                            start=start,end=offset,source_text_start=source_start,source_text_end=offset-2,cells=cells,
                            visual_verification_required=bool(b.get('visual_verification_required') or b['kind']=='figure')))
    return ''.join(pieces),records


def original_excerpt(r2,sid,blocks):
    mapping=load(r2/'maps'/f'{sid}.json');text=(r2/'candidates'/f'{sid}.md').read_text(encoding='utf-8')
    ids={b['id'] for b in blocks};pieces=[];records=[];offset=0
    packets={p['start_in_document']:p for p in mapping['packets']}
    for record in mapping['primary']:
        if record['block_id'] not in ids:continue
        piece=text[record['start']:record['end']];a=offset;pieces.append(piece);offset+=len(piece)
        packet=packets.get(record['start'])
        source_start=a+(piece.index('[Source]\n')+len('[Source]\n') if packet else 0)
        records.append(dict(id=record['block_id'],page=record['page'],kind=record['kind'],start=a,end=offset,
                            source_text_start=source_start,source_text_end=offset-2,dependencies=packet['dependencies'] if packet else [],
                            dependency_characters=packet['dependency_characters'] if packet else 0))
    return ''.join(pieces),records


def aligned_chunks(path,text,strategy):
    chunks=chunk(path,text,strategy);aligned=[];previous=-1
    for c in chunks:
        if strategy=='structure-v2':
            a,z=c.metadata['start_offset'],c.metadata['end_offset'];contexts=c.metadata['context_spans']
            assert c.text[c.metadata['synthetic_chars']:]==text[a:z]
            occurrences=1
        else:
            # Exact, monotone, occurrence-checked alignment; keep ambiguity visible.
            a=text.find(c.text,previous+1)
            if a<0:raise ValueError('Legacy chunk cannot be source-aligned')
            z=a+len(c.text);contexts=[];previous=a
            occurrences=sum(1 for _ in re.finditer(re.escape(c.text),text))
        aligned.append(dict(text=c.text,start=a,end=z,contexts=contexts,occurrences=occurrences,
                            synthetic_chars=c.metadata.get('synthetic_chars',0),limited_context=c.metadata.get('limited_context',False),
                            section_path=c.metadata.get('section_path',[c.metadata.get('section_header','')])))
    return aligned


def retained(dep,c,text,records,nodes,mode):
    if mode=='r2':return flat(dep['text']) in flat(c['text'])
    origin=dep.get('origin_block',dep['id']);record=next((r for r in records if r['id']==origin),None)
    if record is None:return False
    spans=dep.get('source_markdown_spans',[[0,len(nodes[origin]['text'])]])
    # Context spans must really carry the source text; sidecars are NOT retrieval payload.
    visible=[(c['start'],c['end'])]+[tuple(s) for s in c['contexts']]
    for a,z in spans:
        a+=record['source_text_start'];z+=record['source_text_start']
        if not any(x<=a and z<=y for x,y in visible) or flat(text[a:z]) not in flat(c['text']):return False
    return True


def metrics(path,text,strategy,records,blocks,relations,nodes,mode):
    chunks=aligned_chunks(path,text,strategy);by_id={b['id']:b for b in blocks}
    checked=[];procedure_chunks=set();complete=set()
    for i,c in enumerate(chunks):
        requirements=set()
        for r in records:
            if r['kind'] not in ('paragraph','step','menu','table'):continue
            a,z=max(c['start'],r['source_text_start']),min(c['end'],r['source_text_end'])
            if z<=a or not text[a:z].strip():continue
            requirements.update(relations.get(r['id'],[]))
        if requirements:
            procedure_chunks.add(i)
            local=[]
            for dep in sorted(requirements):
                ok=retained(nodes[dep],c,text,records,nodes,mode)
                checked.append(dict(chunk=i,dependency=dep,retained=ok));local.append(ok)
            if all(local):complete.add(i)
    sizes=sorted(len(c['text']) for c in chunks)
    source_spans=[(c['start'],c['end']) for c in chunks]
    covered=set()
    for a,z in source_spans:covered.update(range(a,z))
    nonspace={i for i,v in enumerate(text) if not v.isspace()}
    dependencies={d for b in blocks if b['kind'] in ('paragraph','step','menu','table') for d in relations.get(b['id'],[])}
    union_complete=all(any(retained(nodes[d],c,text,records,nodes,mode) for c in chunks) for d in dependencies)
    # For safety union coverage, several chunks can collectively carry source pieces.
    union_pieces=True
    if mode=='natural':
        by_record={r['id']:r for r in records}
        visible=[(c['start'],c['end']) for c in chunks]+[tuple(s) for c in chunks for s in c['contexts']]
        for d in dependencies:
            dep=nodes[d];origin=dep.get('origin_block',dep['id']);r=by_record.get(origin)
            if r is None:union_pieces=False;continue
            for a,z in dep.get('source_markdown_spans',[[0,len(nodes[origin]['text'])]]):
                union_pieces &= all(any(x<=j<y for x,y in visible) for j in range(r['source_text_start']+a,r['source_text_start']+z) if not text[j].isspace())
    else:union_pieces=union_complete
    result=dict(chunks=len(chunks),min_characters=min(sizes),median_characters=sizes[len(sizes)//2],max_characters=max(sizes),
                delivered_characters=sum(sizes),v2_synthetic_context_characters=sum(c['synthetic_chars'] for c in chunks),
                legacy_overlap_characters=sum(z-a for a,z in source_spans)-len(covered),
                estimated_delivered_tokens_4chars=sum((len(c['text'])+3)//4 for c in chunks),
                limited_context_chunks=sum(c['limited_context'] for c in chunks),ambiguous_alignment_chunks=sum(c['occurrences']>1 for c in chunks),
                missing_nonwhitespace_source_characters=len(nonspace-covered),dependency_checks=len(checked),dependencies_retained=sum(x['retained'] for x in checked),
                procedure_chunks_with_dependencies=len(procedure_chunks),procedure_chunks_all_dependencies=len(complete),
                all_dependency_source_pieces_available_in_document=bool(union_pieces),all_dependencies_whole_somewhere=union_complete)
    return result,chunks,checked


def risk_policy(audit):
    findings=[]
    layout={'merged-or-ambiguous-table-cells','alignment-or-borderless-table-review','rotated-text-review','complex-vector-grid','independent-text-disagreement','lossless-fallback-structure-unresolved'}
    semantics={'callout-applicability-not-certified','inline-condition-applicability-review','unreviewed-dependency-candidates-not-materialized','colored-callout-scope-review'}
    for p in audit['page_records']:
        flags={x['reason'] for x in p['flags']}
        corruption=any(p[k] for k in ('source_lines_missing','duplicate_primary_lines','glyph_lines_missing','table_cells_missing','numeric_values_missing','primary_partition_errors','packet_failures'))
        if corruption:gate='block-detected-retention-defect'
        elif p['severity']=='High' and flags&layout:gate='mandatory-human-text-layout-adjudication'
        elif p['severity']=='High' and flags&semantics:gate='mandatory-human-applicability-adjudication'
        elif p['severity']=='High' and flags=={'substantial-image-visual-review'}:gate='visual-only-candidate-needs-human-disposition'
        elif p['severity']=='High':gate='mandatory-human-other-high-adjudication'
        else:gate='existing-medium-low-not-certified'
        findings.append(dict(source_id=p['source_id'],page=p['page'],original_severity=p['severity'],unique_flags=sorted(flags),
                             proposed_gate=gate,severity_changed=False,disposition='pending; no admission or automatic downgrade'))
    return dict(records=findings,gates=dict(Counter(x['proposed_gate'] for x in findings)),
                unique_page_flag_counts=dict(Counter(f for p in findings for f in p['unique_flags'])))


def run(r2,output):
    corpus=r2.parent/'stage-2b2-real-world-20261111';r1=r2.parent/'stage-2b2-real-world-20261111-r1'
    protected=[r2.resolve(),r1.resolve(),corpus.resolve(),Path(r'C:\ROOT')]
    if any(output.resolve().is_relative_to(p) or p.is_relative_to(output.resolve()) for p in protected):raise ValueError('Separate external output required')
    if any((p/'.obsidian').exists() for p in (output,*output.parents)):raise ValueError('Output must be outside vaults')
    if output.exists():raise ValueError('Choose a new versioned output directory')
    before=verify(r2,corpus,r1,R2_SHA);output.mkdir(parents=True)
    audit=load(r2/'automated-audit.json');risk=risk_policy(audit)
    write(output/'risk-policy-proposals.json',risk)
    with (output/'high-disposition-proposals.csv').open('w',encoding='utf-8',newline='') as file:
        w=csv.writer(file);w.writerow(['source_id','pdf_page','original_severity','proposed_gate','severity_changed','unique_flags'])
        for p in risk['records']:
            if p['original_severity']=='High':w.writerow([p['source_id'],p['page'],p['original_severity'],p['proposed_gate'],False,';'.join(p['unique_flags'])])
    equality=[]
    for u in audit['manuals']:
        p=r2/u['candidate_path'];text=p.read_text(encoding='utf-8');m=load(r2/'maps'/f'{u["id"]}.json')
        legacy=chunk(p,text,'legacy');v2=chunk(p,text,'structure-v2')
        equality.append(dict(source_id=u['id'],packets=len(m['packets']),source_headings=sum(p['kind']=='heading' for p in m['primary']),
                             legacy_chunks=len(legacy),v2_chunks=len(v2),trimmed_chunk_sequence_identical=[c.text.strip() for c in legacy]==[c.text.strip() for c in v2],
                             v2_synthetic_characters=sum(c.metadata['synthetic_chars'] for c in v2)))
    results=[];relationships=load(r2/'dependency-relations.json');relation_lookup={r['id']:r['dependencies'] for r in relationships}
    for sample,sid,sections in SAMPLES:
        pages=[load(p) for p in sorted((r2/'structured'/sid).glob('*.json'))]
        blocks=[b for p in pages for b in p['blocks'] if number(b) in sections]
        mapping=load(r2/'maps'/f'{sid}.json');nodes={b['id']:b for p in pages for b in p['blocks']}
        nodes.update({d['id']:d for d in mapping['derived_dependencies']})
        if not blocks:raise ValueError('Missing selected section')
        data=dict(sample=sample,source_id=sid,sections=list(sections),pages=sorted({b['page'] for b in blocks}),
                  source_blocks=len(blocks),source_pdf_sha256=mapping['source_pdf_sha256'],representations={})
        payloads={};shape_checks=[]
        for mode,builder in [('r2',lambda:original_excerpt(r2,sid,blocks)),('natural',lambda:natural(blocks))]:
            text,records=builder();folder=output/mode;folder.mkdir(exist_ok=True);path=folder/f'{sample}.md';path.write_text(text,encoding='utf-8')
            write(output/'maps'/f'{sample}-{mode}.json',dict(records=records,source_blocks=blocks,
                dependency_nodes=[nodes[d] for d in sorted({d for b in blocks for d in relation_lookup.get(b['id'],[])})],
                relations={b['id']:relation_lookup.get(b['id'],[]) for b in blocks},source_pdf_sha256=mapping['source_pdf_sha256']))
            metric=dict(characters=len(text),bytes=path.stat().st_size,sha256=digest(path),
                        derived_repetition_characters=sum(r.get('dependency_characters',0) for r in records),strategies={})
            for strategy in ('legacy','structure-v2'):
                stats,chunks,checks=metrics(path,text,strategy,records,blocks,relation_lookup,nodes,mode)
                metric['strategies'][strategy]=stats;payloads[mode,strategy]=[c['text'].strip() for c in chunks]
                write(output/'chunk-diagnostics'/f'{sample}-{mode}-{strategy}.json',dict(chunks=chunks,dependency_checks=checks))
            data['representations'][mode]=metric
            if mode=='natural':
                for b,r in zip(blocks,records):
                    own=text[r['start']:r['end']]
                    if b['kind']=='figure':ok='Visual information unavailable' in own
                    elif b['kind']=='menu':ok=all(flat(row['label']) in flat(own) for row in b['rows'])
                    elif b['kind']=='table':ok=all(flat(value or '').replace('\\','') in flat(own).replace('\\','') for row in b['source_rows'] for value in row)
                    else:ok=flat(b['text']) in flat(own)
                    shape_checks.append(dict(id=b['id'],kind=b['kind'],source_text_or_cell_retained=ok))
                write(output/'fidelity'/f'{sample}.json',shape_checks)
                if not all(c['source_text_or_cell_retained'] for c in shape_checks):raise ValueError('Source fidelity regression')
        data['strategies_trimmed_sequence_identical']={m:payloads[m,'legacy']==payloads[m,'structure-v2'] for m in ('r2','natural')}
        data['fidelity_checks']=len(shape_checks);results.append(data)
        print(sample,[(m,data['representations'][m]['characters'],{s:v['chunks'] for s,v in data['representations'][m]['strategies'].items()}) for m in ('r2','natural')],flush=True)
    write(output/'results.json',dict(task='3C.2A-R3A',status='representation-review-only-no-admission',
        sample_selection='Seven complete source-numbered sections/groups chosen for existing menu, cross-page warning, procedure and table layouts before measuring; not a random corpus sample',
        full_r2_equality=equality,samples=results,risk_summary={k:v for k,v in risk.items() if k!='records'},
        dependency_metric_scope='Inherited R2 reviewed relations, query-independent extraction QA; not new gold evidence or independent safety adjudication',
        integrity_before=before,integrity_after=verify(r2,corpus,r1,R2_SHA)))


def finalize(r2,output):
    """Package only this review's artifacts; verify prior workspaces read only."""
    data=load(output/'results.json');test_log=(output/'isolated-tests.txt').read_text(encoding='utf-8')
    passed=re.search(r'(\d+) passed in ([\d.]+)s',test_log)
    if not passed or re.search(r'\b(?:failed|ERROR)\b',test_log):raise ValueError('Passing isolated tests required')
    for sample in data['samples']:
        sample['primary_boundary_equality_after_whitespace_trim']={}
        for mode in ('r2','natural'):
            text=(output/mode/f'{sample["sample"]}.md').read_text(encoding='utf-8');sequences=[]
            for strategy in ('legacy','structure-v2'):
                chunks=load(output/'chunk-diagnostics'/f'{sample["sample"]}-{mode}-{strategy}.json')['chunks']
                intervals=[]
                for c in chunks:
                    a,z=c['start'],c['end']
                    while a<z and text[a].isspace():a+=1
                    while z>a and text[z-1].isspace():z-=1
                    intervals.append([a,z])
                sequences.append(intervals)
            sample['primary_boundary_equality_after_whitespace_trim'][mode]=sequences[0]==sequences[1]
    write(output/'results.json',data)
    repo=Path(__file__).resolve().parents[2]
    files=['tools/corpus/review_prusa_r3a.py','tests/evaluation/test_prusa_pdf_r3a.py',
           'tools/corpus/audit_prusa_r2.py','tools/corpus/finalize_prusa_r2.py','tools/corpus/prusa_pdf_r2.py','tools/corpus/prusa_pdf_remediation.py']
    for relative in files:
        target=output/'reproduction-tools'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/relative,target)
    hashes={p:digest(repo/p) for p in files+['laew/rag/knowledge_base.py','laew/rag/markdown_chunker.py','laew/rag/contextual_chunker.py','scripts/run_isolated.py']}
    manifest=dict(task='3C.2A-R3A',status='representation-review-only-not-admitted-not-frozen',date='2026-11-11',
        input_r2=str(r2),input_inventory_sha256=R2_SHA,scope='Seven excerpt pairs only; no full regeneration',code_sha256=hashes,
        tests=dict(passed=int(passed[1]),seconds=float(passed[2]),runner='scripts/run_isolated.py',log='isolated-tests.txt'),
        license='Local research only; no Prusa handbook redistribution authorization established; source-bearing excerpts/maps/chunk traces stay outside Git',
        prior_input_verification=verify(r2,r2.parent/'stage-2b2-real-world-20261111',r2.parent/'stage-2b2-real-world-20261111-r1',R2_SHA))
    write(output/'review-manifest.json',manifest)
    (output/'README.md').write_text('''# R3A representation review only

`natural/` and `r2/` contain seven corresponding complete selected section/group excerpts, not full manuals.
No source warnings are repeated in `natural/`. Original source headings, one copy of each source paragraph/cell/menu label, and explicit unavailable-visual markers are retained.
`maps/` attributes source IDs, pages, ranges and cells, retaining inherited reviewed dependency relationships. Sidecars are diagnostic only; the production loader does not consume them or deliver them as context.
`chunk-diagnostics/` contains actual dry parser payloads/offsets for both unchanged strategies. These are extraction QA diagnostics, not questions or gold evidence labels.
`high-disposition-proposals.csv` retains all 388 High pages and proposes gates without changing priorities or admitting anything.
Source-bearing material stays local; do not redistribute without licensing approval.

Reproduce in a NEW external output path with the existing LAEW Python environment:
`python -B tools/corpus/review_prusa_r3a.py --r2 <R2-root> --output <new-output>`
Run the documented isolated tests with `LAEW_PRUSA_R3A_ROOT` set to that output, save the passing log as `isolated-tests.txt`, then use the same command with `--finalize` to package evidence.
`reproduction-tools/` snapshots the experiment and its local helper dependencies. Production source hashes are in `review-manifest.json`.

Offline read-only check:
`python -B tools/corpus/review_prusa_r3a.py --r2 <R2-root> --output <R3A-root> --verify --expected-inventory-sha <repository-report-anchor>`
This verifies R3A and the original R2/accepted/R1 inventory chain without downloads or source writes.
''',encoding='utf-8')
    write(output/'r3a-integrity-inventory.json',dict(algorithm='SHA-256',files=[dict(path=p.relative_to(output).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='r3a-integrity-inventory.json']))
    verification=verify_review(r2,output)
    write(repo/'docs/reports/prusa-pdf-r3a-20261111-review.json',dict(**data,manifest=manifest,integrity=verification))
    print(json.dumps(verification,indent=2))


def verify_review(r2,output,expected=None):
    inventory=output/'r3a-integrity-inventory.json'
    if expected and digest(inventory)!=expected:raise ValueError('R3A inventory anchor mismatch')
    records=load(inventory)['files']
    for r in records:
        path=(output/r['path']).resolve()
        if not path.is_relative_to(output.resolve()) or not path.is_file() or path.stat().st_size!=r['bytes'] or digest(path)!=r['sha256']:raise ValueError('R3A mismatch: '+r['path'])
    expected_paths={r['path'] for r in records}|{inventory.name}
    if expected_paths!={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}:raise ValueError('R3A path set changed')
    prior=verify(r2,r2.parent/'stage-2b2-real-world-20261111',r2.parent/'stage-2b2-real-world-20261111-r1',R2_SHA)
    return dict(verified=True,r3a_files=len(records),inventory_sha256=digest(inventory),prior_inputs=prior)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--r2',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    mode=ap.add_mutually_exclusive_group();mode.add_argument('--finalize',action='store_true');mode.add_argument('--verify',action='store_true')
    ap.add_argument('--expected-inventory-sha');a=ap.parse_args()
    if a.finalize:finalize(a.r2,a.output)
    elif a.verify:print(json.dumps(verify_review(a.r2,a.output,a.expected_inventory_sha),indent=2))
    else:run(a.r2,a.output)
