"""Bounded, agent-origin PDF triage; never regenerate a full manual or admit a corpus."""
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
from html import escape

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from review_prusa_r3a import natural,number,verify_review,load,write,digest,R2_SHA,SAMPLES
from prusa_pdf_remediation import rich_line

R3A_SHA='dd7d52fef9b733912c990aac6215c226841bc65bcf0277dd3677f1d3f6c05dfa'
B_PAGES=[('prusa-mk4s-en',10),('prusa-mk4s-en',35),('prusa-mmu3-en',11),('prusa-mmu3-en',41),
         ('prusa-mk4-de',33),('prusa-mk4-de',50),('prusa-xl-de',35),('prusa-xl-de',83),
         ('prusa-mini-pl',16),('prusa-mini-pl',29),('prusa-mk3s-pl',50),('prusa-mk3s-pl',52)]

TABLE_PAGES=[('prusa-mk4-de',7),('prusa-mk4-de',8),('prusa-mk4s-en',6),('prusa-mmu3-en',7),('prusa-xl-de',9),('prusa-xl-de',81)]
# Only visually inspected coordinate regions; not a corpus-wide detector.
COLUMNS=[('prusa-mk3s-pl',16,6,19,320,False),('prusa-mk3s-pl',69,8,12,300,True),
         ('prusa-xl-de',62,24,31,210,True),('prusa-mini-pl',42,19,28,210,True),('prusa-mini-pl',45,2,12,210,False)]
NOTE_RUNS=[('prusa-mk3s-pl',16,0,3),('prusa-mk3s-pl',19,7,11),('prusa-mk3s-pl',47,15,18),('prusa-mk3s-pl',59,25,28)]


def replace_lines(page,indices,replacement):
    """Reassign selected original lines exactly once, retaining all outside lines."""
    target=set(indices);out=[]
    for b in page['blocks']:
        overlap=target&set(b['source_lines'])
        if not overlap:out.append(b);continue
        remaining=[i for i in b['source_lines'] if i not in target]
        if remaining:
            out.append({**b,'source_lines':remaining,'text':' '.join(rich_line(page['lines'][i]) for i in remaining),'top':page['lines'][remaining[0]]['top']})
    out.append(replacement);page['blocks']=sorted(out,key=lambda b:b['top'])


def patch_selected(r2,out):
    import copy
    corpus=r2.parent/'stage-2b2-real-world-20261111';pages={};changes=[]
    native=load(out/'native-repair-objects.json')['records']
    def page(sid,p):
        if (sid,p) not in pages:
            value=load(r2/'geometry'/sid/f'{p:03d}.json');value['blocks']=copy.deepcopy(load(r2/'structured'/sid/f'{p:03d}.json')['blocks']);pages[sid,p]=value
        return pages[sid,p]
    def record(sid,p,kind,indices,detail):changes.append(dict(source_id=sid,page=p,repair=kind,source_lines=list(indices),detail=detail,reviewer_origin='agent',independent_human_certification=False))
    for sid,p in TABLE_PAGES:
        data=page(sid,p)
        table=native[f'{sid}:{p}'];raw=table['rows'];bounds=table['bbox']
        rows=[]
        for row in raw:
            key=row[0];value='\n'.join(v for v in row[1:] if v)
            if key:rows.append([key,value])
            elif rows:rows[-1][1]+='\n'+value
            else:raise ValueError('Orphan merged table row')
        indices=[l['index'] for l in data['lines'] if bounds[1]-1<=l['top'] and l['bottom']<=bounds[3]+1]
        original=''.join(c['text'] for i in indices for c in data['lines'][i]['chars'])
        recovered=''.join(v for row in rows for v in row)
        if Counter(re.sub(r'\s','',original))!=Counter(re.sub(r'\s','',recovered)):
            raise ValueError(f'Table glyph multiset mismatch: {sid}/{p}')
        b=dict(id=f'{sid}:p{p}:r3b-table',source_id=sid,page=p,kind='table',top=bounds[1],source_lines=indices,
               scope=next((b['scope'] for b in data['blocks'] if set(indices)&set(b['source_lines'])),None),
               text='',source_rows=[['','']]+rows,header_verified=True,derived_empty_header=True,source_bbox=bounds,
               native_cells=table['cells'],native_source_rows=raw,
               transformation='Two-column source-labelled matrix; merged value continuations joined within their source label; neutral empty Markdown header is derived',
               source_glyph_multiset_exact=True)
        replace_lines(data,indices,b);record(sid,p,'table-relationships',indices,'Native cell geometry restores label/value order; no value inferred; original merged-cell geometry retained.')
    for sid,p,start,end,cut,header in COLUMNS:
        data=page(sid,p);indices=list(range(start,end+1));columns=[]
        for side in (0,1):
            lines=[];previous=None
            for i in indices:
                row=data['lines'][i];chars=[c for c in row['chars'] if (c['x0']<cut)==(side==0)]
                if not chars:continue
                value=rich_line({**row,'chars':chars})
                new_item=not lines or value.lstrip('*').startswith('•') or (previous is not None and row['top']-previous['top']>row['font_size']*1.6)
                if new_item:lines.append(value)
                else:lines[-1]+=' '+value
                previous=row
            columns.append(lines)
        if header:
            text='\n\n'.join(columns[0])+'\n\n'+'\n\n'.join(columns[1])
        else:
            text='[Derived layout: source left column; graphic marker meaning unavailable in text.]\n\n'+'\n\n'.join(columns[0])+'\n\n[Derived layout: source right column; graphic marker meaning unavailable in text.]\n\n'+'\n\n'.join(columns[1])
        b=dict(id=f'{sid}:p{p}:r3b-columns',source_id=sid,page=p,kind='paragraph',top=data['lines'][start]['top'],source_lines=indices,
               scope=next(b['scope'] for b in data['blocks'] if start in b['source_lines']),text=text,
               source_columns=columns,column_cut=cut,column_semantics='literal-source-headings' if header else 'graphic-polarity-unavailable',
               visual_verification_required=not header)
        replace_lines(data,indices,b);record(sid,p,'column-reading-order',indices,'Read each source text column independently; no checkmark/exclamation semantics invented.')
    for sid,p,start,end in NOTE_RUNS:
        data=page(sid,p);indices=list(range(start,end+1));text=' '.join(rich_line(data['lines'][i]) for i in indices)
        b=dict(id=f'{sid}:p{p}:r3b-note-{start}',source_id=sid,page=p,kind='icon-note',top=data['lines'][start]['top'],source_lines=indices,
               scope=next(b['scope'] for b in data['blocks'] if start in b['source_lines']),text=text)
        replace_lines(data,indices,b);record(sid,p,'complete-callout-paragraph',indices,'Reattach literal final line to its original icon-adjacent paragraph; retain source wording once.')
    data=page('prusa-mk3s-pl',16)
    replace_lines(data,[4,5],dict(id='prusa-mk3s-pl:p16:r3b-heading',source_id=data['id'],page=16,kind='heading',top=data['lines'][4]['top'],source_lines=[4,5],scope='6.3.2.1',text='#### '+' '.join(rich_line(data['lines'][i]) for i in [4,5])))
    record(data['id'],16,'multiline-heading',[4,5],'Restore complete original heading including PEI line.')
    data=page('prusa-mk3s-pl',11)
    heading=next(b for b in data['blocks'] if b['text']=='6 Pierwsze kroki');heading.update(kind='heading',text='# '+heading['text'])
    record(data['id'],11,'chapter-heading',heading['source_lines'],'Restore source chapter heading; do not create artificial packet boundaries.')
    for sid in ['prusa-mini-pl','prusa-mk4-de','prusa-mk4s-en','prusa-mmu3-en','prusa-xl-de']:
        data=page(sid,1)
        correct=native[f'{sid}:1']['rotated_native_text']
        if not correct:raise ValueError('Expected rotated native text')
        reverse=correct[::-1]
        b=next(b for b in data['blocks'] if reverse in b['text']);b['text']=b['text'].replace(reverse,correct)
        b['rotated_source_object_text']=correct
        record(sid,1,'rotated-native-text',b['source_lines'],'Recover native rotated object order, verified against cover render; raster-only cover content remains unavailable.')
    results=[]
    for (sid,p),data in sorted(pages.items()):
        # Every retained source line still has one primary owner.
        original=load(r2/'structured'/sid/f'{p:03d}.json');before=Counter(i for b in original['blocks'] for i in b['source_lines']);after=Counter(i for b in data['blocks'] for i in b['source_lines'])
        if before!=after or any(n!=1 for n in after.values()):raise ValueError('Source ownership changed')
        text,mapping=natural(data['blocks']);path=out/'corrected-excerpts'/f'{sid}-p{p:03d}.md';path.parent.mkdir(exist_ok=True);path.write_text(text,encoding='utf-8')
        write(out/'corrected-maps'/f'{sid}-p{p:03d}.json',dict(source_blocks=data['blocks'],records=mapping,source_line_ownership_exact=True,
                source_pdf_sha256=digest(corpus/'originals'/f'{sid}.pdf'),source_structured_sha256=digest(r2/'structured'/sid/f'{p:03d}.json')))
        results.append(dict(source_id=sid,page=p,path=path.relative_to(out).as_posix(),sha256=digest(path),source_line_ownership_exact=True))
    write(out/'experimental-corrections.json',dict(changes=changes,pages=results,scope='Only inspected page excerpts; no full-manual regeneration or admission'))
    print(json.dumps(dict(corrected_excerpt_pages=len(results),repair_records=len(changes)),indent=2))


def prepare(r2,r3a,out):
    if out.exists():raise ValueError('New versioned experimental workspace required')
    protected=[r2.resolve(),r3a.resolve(),r2.parent/'stage-2b2-real-world-20261111',r2.parent/'stage-2b2-real-world-20261111-r1',Path(r'C:\ROOT')]
    if any(out.resolve().is_relative_to(p) or p.is_relative_to(out.resolve()) for p in protected):raise ValueError('Separate external output required')
    if any((p/'.obsidian').exists() for p in (out,*out.parents)):raise ValueError('Vault output prohibited')
    verified=verify_review(r2,r3a,R3A_SHA)
    risks=load(r3a/'risk-policy-proposals.json')['records'];by_page={(p['source_id'],p['page']):p for p in risks}
    a=sorted({(p['source_id'],p['page']) for p in risks if {'merged-or-ambiguous-table-cells','independent-text-disagreement'}&set(p['unique_flags'])}|{('prusa-mk3s-pl',16),('prusa-xl-de',62)})
    assert len(a)==36
    assert all(by_page[p]['proposed_gate']=='visual-only-candidate-needs-human-disposition' for p in B_PAGES)
    groups=[];c=set()
    for sample,sid,sections in SAMPLES[:6]:
        blocks=[b for file in sorted((r2/'structured'/sid).glob('*.json')) for b in load(file)['blocks'] if number(b) in sections]
        pages=sorted({b['page'] for b in blocks});c.update((sid,p) for p in pages)
        groups.append(dict(id=sample,source_id=sid,sections=sections,pages=pages,block_ids=[b['id'] for b in blocks]))
    selected=sorted(set(a)|set(B_PAGES)|c);out.mkdir(parents=True)
    write(out/'integrity-before.json',verified)
    entries=[]
    for sid,p in selected:
        data=load(r2/'structured'/sid/f'{p:03d}.json');text,mapping=natural(data['blocks'])
        name=f'{sid}-p{p:03d}';target=out/'page-excerpts'/f'{name}.md';target.parent.mkdir(exist_ok=True);target.write_text(text,encoding='utf-8')
        write(out/'page-maps'/f'{name}.json',dict(records=mapping,source_blocks=data['blocks']))
        phases=[phase for phase,members in [('A',set(a)),('B',set(B_PAGES)),('C',c)] if (sid,p) in members]
        risk=by_page[sid,p]
        entries.append(dict(source_id=sid,page=p,phases=phases,original_category=risk['proposed_gate'],original_severity=risk['original_severity'],flags=risk['unique_flags'],
                            original_render=str(r2/'page-renders'/sid/f'page-{p:03d}.png'),render_sha256=digest(r2/'page-renders'/sid/f'page-{p:03d}.png'),
                            original_structured_sha256=digest(r2/'structured'/sid/f'{p:03d}.json'),excerpt_path=target.relative_to(out).as_posix(),excerpt_sha256=digest(target)))
    write(out/'review-selection.json',dict(A=a,B=B_PAGES,C=groups,selected_pages=len(selected),entries=entries,
        scope='36 priority text pages, 12 of 43 visual-only candidates, six procedure groups; all remaining findings stay open'))
    print(json.dumps(dict(selected_pages=len(selected),A=len(a),B=len(B_PAGES),C_groups=len(groups),C_pages=len(c)),indent=2))


def document_review(r2,r3a,out):
    from prusa_r3b_review_notes import A_NOTES,B_NOTES,C_NOTES,GROUP_SCOPES,UNRESOLVED,CORRECTED
    selection=load(out/'review-selection.json');repairs=load(out/'experimental-corrections.json')
    corrected={(p['source_id'],p['page']):p for p in repairs['pages']};notes={**A_NOTES,**B_NOTES,**C_NOTES}
    if set(notes)!={(p['source_id'],p['page']) for p in selection['entries']}:raise ValueError('Explicit review required for every selected page')
    records=[]
    essential={('prusa-mk4-de',33),('prusa-xl-de',35),('prusa-xl-de',83),('prusa-mk3s-pl',16),('prusa-mini-pl',45),('prusa-mk4s-en',19),('prusa-mk4-de',22),('prusa-mmu3-en',6),('prusa-xl-de',81)}
    for entry in selection['entries']:
        key=entry['source_id'],entry['page'];outcome,observation=notes[key];patched=key in corrected
        visual_limit=any(w in observation.lower() for w in ('unavailable','graphic','raster','screenshot','photograph'))
        records.append({**entry,'finding_id':f'{key[0]}:p{key[1]}:r3b-inspection','outcome':outcome,
            'inspection_method':['Agent visual read of original 1400-pixel PDF render','Compared actual source-once excerpt and retained extraction blocks','Native cell/glyph coordinates and corrected excerpt checked where repaired'],
            'finding_and_reason':observation,'source_text_needs_correction':True if patched else None if key==('prusa-mk3s-pl',37) else False,
            'confirmed_extraction_defect':patched,'experimental_correction_applied':patched,'corrected_excerpt':corrected.get(key),
            'blocks_unqualified_text_only_use':outcome==UNRESOLVED,
            'human_review_required':outcome==UNRESOLVED or key in set(TABLE_PAGES) or key==('prusa-xl-de',83),
            'reviewer_origin':'agent','independent_human_certification':False,'original_priority_changed':False,
            'remaining_uncertainty':('Qualified human disposition or explicit passage quarantine required.' if outcome==UNRESOLVED else 'Agent component review only; no whole-page admission or independent human certification.'),
            'visual_availability':dict(surrounding_text_independently_meaningful=outcome!=UNRESOLVED or key in [('prusa-mk3s-pl',37),('prusa-xl-de',81)],
                image_only_information=visual_limit or key in essential,essential_for_some_source_operations=key in essential,
                misleading_without_availability_limit=key in essential,graphic_information_delivered_as_text=False),
            'phase_scope':'Inspected components described above; other flags on this page are not automatically closed'})
    write(out/'inspection-decisions.json',dict(reviewer_origin='agent',records=records))
    availability=[]
    for r in records:
        if not r['blocks_unqualified_text_only_use']:continue
        sid,p=r['source_id'],r['page'];corrected_map=out/'corrected-maps'/f'{sid}-p{p:03d}.json'
        blocks=load(corrected_map)['source_blocks'] if corrected_map.exists() else load(r2/'structured'/sid/f'{p:03d}.json')['blocks']
        if (sid,p) in [('prusa-mk3s-pl',16),('prusa-mini-pl',45)]:affected=[b for b in blocks if b.get('source_columns')]
        elif (sid,p)==('prusa-mk3s-pl',37):affected=[b for b in blocks if '999%' in b['text'] or b['text'].endswith('Obracając')]
        elif (sid,p)==('prusa-xl-de',81):affected=[b for b in blocks if b['kind']=='table' and not b.get('derived_empty_header')]
        elif (sid,p)==('prusa-mmu3-en',6):affected=[b for b in blocks if b['kind']!='heading']
        elif (sid,p) in [('prusa-mk4-de',33),('prusa-xl-de',35)]:
            reset_section='4.13' if sid=='prusa-mk4-de' else '4.14'
            affected=[b for b in blocks if number(b)==reset_section and b['kind']!='heading']
        else:affected=[b for b in blocks if b['kind']=='figure' or 'filament' in b['text'].lower() and b['kind']=='paragraph']
        if not affected:raise ValueError('Unresolved case needs exact source region')
        marker=f'[Derived text-only availability limitation: source relationships or image-dependent procedural information remain unresolved on PDF page {p}. Original text is retained; this region is not verified as complete procedural or graphical support.]'
        # Keep all original text. A local marker identifies unavailable support; no technical advice or image description is generated.
        patched=[];inserted=False
        for b in blocks:
            if not inserted and b['id'] in {a['id'] for a in affected}:
                patched.append(dict(id=f'{sid}:p{p}:r3b-availability',kind='paragraph',source_lines=[],scope=b['scope'],text=marker,page=p));inserted=True
            patched.append(b)
        text,mapping=natural(patched);path=out/'availability-excerpts'/f'{sid}-p{p:03d}.md';path.parent.mkdir(exist_ok=True);path.write_text(text,encoding='utf-8')
        availability.append(dict(source_id=sid,page=p,source_block_ids=[b['id'] for b in affected],
            source_line_ids=sorted({i for b in affected for i in b['source_lines']}),restriction='not-verified-as-complete-procedural-or-graphical-support',
            original_text_retained=True,reviewer_origin='agent',manual_review_required=True,excerpt_path=path.relative_to(out).as_posix(),mapping=mapping,
            note='Scope decision proposal, not corpus admission or future question/evidence labels; unrelated text remains available for separate disposition'))
    write(out/'availability-register.json',availability)
    groups=[]
    for group in selection['C']:
        sid=group['source_id'];blocks=[]
        for p in group['pages']:
            patched=out/'corrected-maps'/f'{sid}-p{p:03d}.json'
            source=load(patched)['source_blocks'] if patched.exists() else load(r2/'structured'/sid/f'{p:03d}.json')['blocks']
            blocks.extend(b for b in source if number(b) in group['sections'])
        text,mapping=natural(blocks);target=out/'procedure-excerpts'/f'{group["id"]}.md';target.parent.mkdir(exist_ok=True);target.write_text(text,encoding='utf-8')
        sidecar={**group,'reviewer_origin':'agent','independent_human_certification':False,'outcome':'Verified correct',
            'verification_scope':'Original text/relationship scope only; not a complete operational or graphical certification',
            'applicability_decision':GROUP_SCOPES[group['id']],
            'warning_source_ids':[b['id'] for b in blocks if b['kind'] in ('warning','information','icon-note','callout')],
            'inline_condition_source_ids':[b['id'] for b in blocks if b['kind']=='paragraph' and '**' in b['text']],
            'source_blocks_once':[b['id'] for b in blocks], 'mapping':mapping,
            'representation':'Source warnings in original positions once; no per-chunk propagation; sidecar not consumed by production renderer',
            'unresolved_graphical_substeps':[r['page'] for r in records if r['source_id']==sid and r['page'] in group['pages'] and r['blocks_unqualified_text_only_use']]}
        write(out/'procedure-sidecars'/f'{group["id"]}.json',sidecar);groups.append({k:v for k,v in sidecar.items() if k!='mapping'})
    write(out/'procedure-decisions.json',groups)
    inherited=load(r3a/'risk-policy-proposals.json')['records'];lookup={(r['source_id'],r['page']):r for r in records}
    risk=[]
    for p in inherited:
        record=lookup.get((p['source_id'],p['page']))
        risk.append({**p,'r3b_inspected':bool(record),'r3b_outcome':record['outcome'] if record else None,
                     'admission_status':'not-admitted','human_certified':False,'priority_changed':False})
    write(out/'outstanding-risk-register.json',risk)
    with (out/'uninspected-high.csv').open('w',encoding='utf-8',newline='') as file:
        w=csv.writer(file);w.writerow(['source_id','pdf_page','original_category','flags'])
        for p in risk:
            if p['original_severity']=='High' and not p['r3b_inspected']:w.writerow([p['source_id'],p['page'],p['proposed_gate'],';'.join(p['unique_flags'])])
    with (out/'inspection-decisions.csv').open('w',encoding='utf-8',newline='') as file:
        w=csv.writer(file);w.writerow(['source_id','pdf_page','phases','original_category','outcome','source_text_needs_correction','experimental_correction','blocks_unqualified_text_only_use','human_review_required','reviewer_origin','finding_and_reason'])
        for r in records:w.writerow([r[k] if k!='phases' else ','.join(r[k]) for k in ['source_id','page','phases','original_category','outcome','source_text_needs_correction','experimental_correction_applied','blocks_unqualified_text_only_use','human_review_required','reviewer_origin','finding_and_reason']])
    # Size estimator uses paired reviewed pages. Chunk-density scenarios use complete R3A sections, not artificial page files.
    r2audit=load(r2/'automated-audit.json');estimates=[]
    for m in r2audit['manuals']:
        sid=m['id'];selected={r['page'] for r in records if r['source_id']==sid};mapping=load(r2/'maps'/f'{sid}.json')
        denominator=sum(len(c['text']) for c in mapping['components'] if c['page'] in selected)
        denominator+=sum(len(b['text']) for p in selected for b in load(r2/'structured'/sid/f'{p:03d}.json')['blocks'] if b['kind']=='heading')
        numerator=sum(len((out/(corrected[sid,p]['path'] if (sid,p) in corrected else f'page-excerpts/{sid}-p{p:03d}.md')).read_text(encoding='utf-8')) for p in selected)
        ratio=numerator/denominator
        estimates.append(dict(source_id=sid,reviewed_pages=len(selected),paired_r2_primary_characters=denominator,source_once_characters=numerator,
                              ratio=ratio,estimated_full_source_once_characters=round(m['primary_representation_characters']*ratio)))
    central=sum(e['estimated_full_source_once_characters'] for e in estimates);lo=round(central*.85);hi=round(central*1.15)
    r3results=load(r3a/'results.json');scenarios={}
    for strategy in ('legacy','structure-v2'):
        densities=[s['representations']['natural']['strategies'][strategy]['chunks']/s['representations']['natural']['characters'] for s in r3results['samples']]
        scenarios[strategy]=dict(min_sample_chunks_per_1000_characters=min(densities)*1000,max_sample_chunks_per_1000_characters=max(densities)*1000,
            full_24_source_chunks_low=round(lo*min(densities))+806,full_24_source_chunks_high=round(hi*max(densities))+806,
            note='Scenario, not confidence interval or full dry ingestion; fixed 806 unchanged text-source chunks; biased sample and new formatting can shift counts beyond this band')
    resource=dict(paired_page_samples=estimates,prusa_point_characters=central,prusa_sensitivity_characters=[lo,hi],
        unchanged_18_body_characters=465842,total_24_sensitivity_characters=[lo+465842,hi+465842],chunk_scenarios=scenarios,
        limitation='Purposive high-risk sample, no random sampling, no full regeneration. +/-15% is an explicit planning assumption, not measured uncertainty. 3000 is a resource review trigger, not validity limit.')
    write(out/'resource-estimate.json',resource)
    html=['<!doctype html><meta charset="utf-8"><title>R3B bounded triage</title><style>body{font:15px system-ui;margin:2em}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1em}img{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:2px solid #888;margin:2em 0}</style><h1>R3B agent-origin component triage; no admission</h1>']
    for r in records:
        before=(out/r['excerpt_path']).read_text(encoding='utf-8');after=(out/r['corrected_excerpt']['path']).read_text(encoding='utf-8') if r['corrected_excerpt'] else None
        html.append('<section><h2>'+escape(f'{r["source_id"]} / PDF {r["page"]}: {r["outcome"]}')+'</h2><p>'+escape(r['finding_and_reason'])+'</p><div class="pair"><div><img loading="lazy" src="'+Path(r['original_render']).as_uri()+'"></div><div><details'+('' if after else ' open')+'><summary>Actual initial excerpt</summary><pre>'+escape(before)+'</pre></details>'+('<h3>Corrected experimental excerpt</h3><pre>'+escape(after)+'</pre>' if after else '')+'</div></div></section>')
    (out/'review.html').write_text('\n'.join(html),encoding='utf-8')
    summary=dict(task='3C.2A-R3B',status='bounded-agent-triage-only-no-admission',inspected_pages=len(records),
        phase_counts={'A':36,'B':12,'C_groups':6,'C_pages':13,'overlap_pages':1},outcome_counts=dict(Counter(r['outcome'] for r in records)),
        phase_outcome_counts={p:dict(Counter(r['outcome'] for r in records if p in r['phases'])) for p in ('A','B','C')},
        experimental_correction_pages=len(corrected),experimental_repair_records=len(repairs['changes']),
        unresolved_inspected_pages=[dict(source_id=r['source_id'],page=r['page'],reason=r['finding_and_reason']) for r in records if r['blocks_unqualified_text_only_use']],
        mandatory_human_review_pages=[dict(source_id=r['source_id'],page=r['page']) for r in records if r['human_review_required']],
        original_severity_counts=dict(Counter(p['original_severity'] for p in inherited)),uninspected_high=sum(p['original_severity']=='High' and not p['r3b_inspected'] for p in risk),
        uninspected_visual_only_candidates=43-12,human_certifications=0,resource_estimate=resource,
        integrity_after=verify_review(r2,r3a,R3A_SHA))
    write(out/'triage-results.json',summary);print(json.dumps({k:v for k,v in summary.items() if k in ('inspected_pages','outcome_counts','uninspected_high','experimental_correction_pages','mandatory_human_review_pages')},indent=2))


def verify_triage(r2,r3a,out,expected=None):
    inventory=out/'r3b-integrity-inventory.json'
    if expected and digest(inventory)!=expected:raise ValueError('R3B inventory anchor mismatch')
    items=load(inventory)['files']
    for item in items:
        path=(out/item['path']).resolve()
        if not path.is_relative_to(out.resolve()) or not path.is_file() or path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:raise ValueError('R3B integrity mismatch: '+item['path'])
    if {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}!={p['path'] for p in items}|{inventory.name}:raise ValueError('R3B path set changed')
    return dict(verified=True,r3b_files=len(items),inventory_sha256=digest(inventory),prior_inputs=verify_review(r2,r3a,R3A_SHA))


def package(r2,r3a,out):
    summary=load(out/'triage-results.json');test_log=(out/'isolated-tests.txt').read_text(encoding='utf-8');passed=re.search(r'(\d+) passed in ([\d.]+)s',test_log)
    if not passed or re.search(r'\b(?:failed|ERROR)\b',test_log):raise ValueError('Passing isolated tests required')
    repo=Path(__file__).resolve().parents[2]
    files=['tools/corpus/triage_prusa_r3b.py','tools/corpus/prusa_native_repair_objects.py','tools/corpus/prusa_r3b_review_notes.py','tests/evaluation/test_prusa_pdf_r3b.py']
    for name in files:
        target=out/'reproduction-tools'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/name,target)
    dependencies=['tools/corpus/review_prusa_r3a.py','tools/corpus/prusa_pdf_r2.py','tools/corpus/prusa_pdf_remediation.py','tools/corpus/finalize_prusa_r2.py','tools/corpus/audit_prusa_r2.py','laew/rag/knowledge_base.py','laew/rag/markdown_chunker.py','laew/rag/contextual_chunker.py','scripts/run_isolated.py']
    integrity_after=verify_review(r2,r3a,R3A_SHA)
    if integrity_after!=load(out/'integrity-before.json'):raise ValueError('Prior input integrity changed')
    write(out/'integrity-after.json',integrity_after)
    manifest=dict(task='3C.2A-R3B',status='bounded-agent-triage-only-not-admitted-not-frozen',date='2026-11-11',input_r2=str(r2),input_r3a=str(r3a),
        r2_inventory_sha256=R2_SHA,r3a_inventory_sha256=R3A_SHA,reviewer_origin='agent',independent_human_certifications=0,
        source_selection_preserved=24,scope='60 page excerpts; 20 corrected page excerpts; 9 availability examples; 6 source-once procedure groups; no complete manual',
        tools={'native_pdf_python':'3.12.14','pdfplumber':'0.11.9','qa_python':'3.14.7','renders':'Unchanged R2 Poppler 26.07.0 source renders'},
        tests=dict(passed=int(passed[1]),seconds=float(passed[2]),runner='scripts/run_isolated.py',log='isolated-tests.txt'),
        code_sha256={name:digest(repo/name) for name in files+dependencies},
        license='No Prusa handbook redistribution grant established; source-bearing excerpts, maps, native objects and viewer stay in local staging',
        limits='No OCR, generated visual descriptions, chunker/retrieval changes, inference, questions, labels, embeddings, ChromaDB, admission, freeze or full regeneration')
    write(out/'triage-manifest.json',manifest)
    write(out/'admission-policy-proposal.json',dict(status='proposal-only-no-admission',cases=[
        dict(case=1,kind='valid-text-split-across-chunks',policy='Potentially compatible. Preserve source spans and original conditions; assess only actually delivered text later. Do not repeat warnings to force identical chunk boundaries.'),
        dict(case=2,kind='valid-text-with-unavailable-graphics',policy='Potentially compatible after explicit availability/scope approval. Retain captions and prose, identify original page/region, do not claim complete graphical or procedural support.'),
        dict(case=3,kind='incorrect-or-incomplete-native-text',policy='Blocks affected support until corrected and verified, quarantined by source region, or covered by a separately approved scope decision. Keep original text and full documents; no silent cropping.'),
        dict(case=4,kind='unresolved-safety-table-or-applicability-meaning',policy='Requires qualified human disposition or explicit source-region quarantine/scope approval before use as complete support. Agent inspection is not independent human certification.')],
        next_task_scope='R3C proposed: complete source-once candidate regeneration only, exact reviewed repair overlays, explicit unresolved availability records and unchanged open priorities; no admission, freeze, questions, labels or indexing.',
        requirements=['Preserve all 24 source units, authentic mixed-language passages and pinned PostgreSQL WAL revision',
                      'Apply 22 demonstrated repairs on 20 pages using exact PDF/source hashes and retain originals',
                      'Carry nine unresolved-region restrictions and all uninspected findings; human review gates remain open',
                      'Do not replace source-once representation with R2 H6 packets or per-chunk safety repetition',
                      'Keep production size, overlap, context and retrieval settings unchanged; review actual resource counts if exceeding 3000 per strategy']))
    (out/'README.md').write_text('''# R3B bounded PDF triage, agent origin only

`review.html` shows each inspected original PDF page beside actual and corrected excerpts. Original renders remain at the pinned R2 path.
`inspection-decisions.json` / CSV record all 60 explicit page/component decisions. These are agent inspections, not independent human certification.
`experimental-corrections.json`, `corrected-excerpts/`, `corrected-maps/` contain only selected source-object/geometry repairs.
`availability-register.json` / `availability-excerpts/` identify nine unresolved regions, retain all text and propose limits on complete procedural/graphical support. No passage has been admitted or removed.
`procedure-sidecars/` record six reviewed original scopes. Warnings stay once in source positions, not in every chunk.
`outstanding-risk-register.json` preserves all 418 priorities. `uninspected-high.csv` lists 329 untouched High pages; no analogous-page auto-closure occurs.
`resource-estimate.json` is an explicitly uncertain sample projection, not full-manual generation or indexing.

Reproduce into a NEW external output: run `triage_prusa_r3b.py` with `--r2`, `--r3a`, `--output` to prepare the bounded excerpts; extract native repair objects using `prusa_native_repair_objects.py` under the bundled Python with pdfplumber; then use `--patch-selected` and `--document-review` under the LAEW Python environment. The explicit agent observations are snapshotted in `reproduction-tools/`; reproducing transformations does not independently reproduce or certify visual judgments.
Run the documented tests through `scripts/run_isolated.py`, save the passing log as `isolated-tests.txt`, then use `--package`. Existing helper/production source hashes are in the manifest and prior R2/R3A snapshots.
Offline check: `python -B tools/corpus/triage_prusa_r3b.py --r2 <R2> --r3a <R3A> --output <R3B> --verify --expected-inventory-sha <repository-report-anchor>`.
This verifies R3B and all prior corpus inventories without downloading or rewriting anything. Use local research storage only; do not redistribute source text or renders without licensing approval.
''',encoding='utf-8')
    write(out/'r3b-integrity-inventory.json',dict(algorithm='SHA-256',files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='r3b-integrity-inventory.json']))
    result=verify_triage(r2,r3a,out)
    # Metadata only; no source paragraphs, native objects or rendered pages copied to Git.
    decisions=load(out/'inspection-decisions.json')['records'];export_records=[]
    for r in decisions:
        export_records.append({k:v for k,v in r.items() if k not in ('corrected_excerpt',)})
    write(repo/'docs/reports/prusa-pdf-r3b-20261111-triage.json',dict(summary=summary,manifest=manifest,integrity=result,decisions=export_records))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--r2',type=Path,required=True);ap.add_argument('--r3a',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    mode=ap.add_mutually_exclusive_group();mode.add_argument('--patch-selected',action='store_true');mode.add_argument('--document-review',action='store_true');mode.add_argument('--package',action='store_true');mode.add_argument('--verify',action='store_true')
    ap.add_argument('--expected-inventory-sha');a=ap.parse_args()
    if a.patch_selected:patch_selected(a.r2,a.output)
    elif a.document_review:document_review(a.r2,a.r3a,a.output)
    elif a.package:package(a.r2,a.r3a,a.output)
    elif a.verify:print(json.dumps(verify_triage(a.r2,a.r3a,a.output,a.expected_inventory_sha),indent=2))
    else:prepare(a.r2,a.r3a,a.output)
