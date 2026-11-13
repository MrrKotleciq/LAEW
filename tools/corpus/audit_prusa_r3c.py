"""Offline all-page fidelity and actual unchanged loader diagnostics for R3C."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import inspect
from itertools import zip_longest
import json
from pathlib import Path
import re
import statistics
import sys
from html import escape
from urllib.parse import unquote

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from laew.rag.knowledge_base import KnowledgeBase
from regenerate_prusa_r3c import load,write,digest
from audit_prusa_r2 import flat
from prusa_pdf_remediation import rich_line


def actual_chunks(path,text,strategy):
    """Trace legacy source offsets without replacing its algorithm or output."""
    kb=object.__new__(KnowledgeBase);kb.chunk_size=1000;kb.chunk_overlap=200;kb.chunking_strategy=strategy
    body=kb._strip_frontmatter(text);offset=len(text)-len(body);calls=[]
    function=KnowledgeBase._chunk_text;lines,first=inspect.getsourcelines(function)
    append_line=first+next(i for i,line in enumerate(lines) if 'chunks.append(chunk)' in line)
    def tracer(frame,event,arg):
        if frame.f_code is not function.__code__:return None
        if event=='call':calls.append(dict(text=frame.f_locals['text'],spans=[]))
        elif event=='line' and frame.f_lineno==append_line:
            value=frame.f_locals;raw=value['text'][value['start']:value['end']]
            a=value['start']+len(raw)-len(raw.lstrip());z=min(value['end'],len(value['text']))-(len(raw)-len(raw.rstrip()))
            calls[-1]['spans'].append((a,z))
        elif event=='return' and arg and not calls[-1]['spans']:
            calls[-1]['spans']=[(0,len(frame.f_locals['text']))]
        return tracer
    previous=sys.gettrace()
    try:
        if strategy=='legacy':sys.settrace(tracer)
        chunks=kb._load_file(path,'global',path.parent,content=text,embed=False)
    finally:
        if strategy=='legacy':sys.settrace(previous)
    records=[]
    if strategy=='legacy':
        sections=kb._extract_sections(body);cursor=0;bases=[]
        if len(calls)!=len(sections):raise ValueError('Legacy instrumentation call mismatch')
        for call,(section,_) in zip(calls,sections):
            if call['text']!=section:raise ValueError('Legacy section trace mismatch')
            a=body.find(section,cursor)
            if a<0:raise ValueError('Legacy section attribution failed')
            bases.append(offset+a);cursor=a+len(section)
        for c in chunks:
            index=c.metadata['section_index'];a,z=calls[index]['spans'][c.metadata['chunk_index']]
            a+=bases[index];z+=bases[index]
            if text[a:z]!=c.text:raise ValueError('Legacy payload/source trace mismatch')
            records.append(dict(start=a,end=z,text=c.text,contexts=[],synthetic_chars=0,limited_context=False))
    else:
        for c in chunks:
            m=c.metadata;a,z=m['start_offset'],m['end_offset']
            if c.text[m['synthetic_chars']:]!=text[a:z]:raise ValueError('V2 source attribution mismatch')
            records.append(dict(start=a,end=z,text=c.text,contexts=m['context_spans'],synthetic_chars=m['synthetic_chars'],limited_context=m['limited_context']))
    if any(c.embedding is not None for c in chunks):raise ValueError('Unexpected embedding')
    return records,offset


def merge_intervals(intervals):
    merged=[]
    for a,z in sorted(intervals):
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(z,merged[-1][1]))
        else:merged.append((a,z))
    return merged


def distribution(values):
    values=sorted(values)
    def percentile(p):return values[round((len(values)-1)*p)] if values else 0
    return dict(count=len(values),min=min(values,default=0),p10=percentile(.10),median=statistics.median(values) if values else 0,
                p90=percentile(.90),p95=percentile(.95),max=max(values,default=0),under_200=sum(v<200 for v in values))


def trimmed_intervals(records,text):
    result=[]
    for c in records:
        a,z=c['start'],c['end']
        while a<z and text[a].isspace():a+=1
        while z>a and text[z-1].isspace():z-=1
        result.append((a,z))
    return result


def chunk_metrics(path,text,source_map=None):
    stats={};strategies={};all_sizes={}
    for strategy in ('legacy','structure-v2'):
        chunks,body_offset=actual_chunks(path,text,strategy);strategies[strategy]=chunks
        spans=[(c['start'],c['end']) for c in chunks];merged=merge_intervals(spans)
        covered=sum(z-a for a,z in merged);cursor=body_offset;missing=[]
        for a,z in merged:
            if a>cursor and text[cursor:a].strip():missing.append([cursor,a])
            cursor=max(cursor,z)
        if text[cursor:].strip():missing.append([cursor,len(text)])
        joins=[]
        for index,c in enumerate(chunks):
            visible=[(c['start'],c['end'])]+[tuple(v) for v in c['contexts']]
            if any(not body_offset<=a<z<=len(text) for a,z in visible):raise ValueError('Invalid source/context offset')
            blocks=[]
            if source_map:
                blocks=[dict(id=b['id'],page=b['page']) for b in source_map['records'] if any(a<b['end'] and b['start']<z for a,z in visible)]
            joins.append(dict(index=index,start=c['start'],end=c['end'],context_spans=c['contexts'],synthetic_chars=c['synthetic_chars'],
                              limited_context=c['limited_context'],text_sha256=__import__('hashlib').sha256(c['text'].encode()).hexdigest(),source_blocks=blocks))
        sizes=[len(c['text']) for c in chunks];all_sizes[strategy]=sizes
        stats[strategy]=dict(chunks=len(chunks),sizes=distribution(sizes),delivered_characters=sum(sizes),
            primary_span_characters=sum(z-a for a,z in spans),unique_primary_span_characters=covered,
            added_overlap_characters=sum(z-a for a,z in spans)-covered,added_context_characters=sum(c['synthetic_chars'] for c in chunks),
            limited_context_chunks=sum(c['limited_context'] for c in chunks),missing_nonwhitespace_ranges=missing,
            source_partition_exact=(''.join(text[a:z] for a,z in spans)==text[body_offset:]) if strategy=='structure-v2' else None,
            estimated_delivered_tokens_4chars=sum((v+3)//4 for v in sizes),source_attribution='Exact actual-engine trace (legacy) / native offsets and context spans (V2)')
        strategies[strategy+'_joins']=joins
    legacy,v2=strategies['legacy'],strategies['structure-v2']
    a=trimmed_intervals(legacy,text);b=trimmed_intervals(v2,text)
    # Counts describe partition/payload differences, not relevance or recall.
    ends_a={z for _,z in a[:-1]};ends_b={z for _,z in b[:-1]}
    ca=Counter(c['text'].strip() for c in legacy);cb=Counter(c['text'].strip() for c in v2);shared=sum((ca&cb).values())
    comparison=dict(trimmed_primary_intervals_identical=a==b,trimmed_payload_sequence_identical=[c['text'].strip() for c in legacy]==[c['text'].strip() for c in v2],
        common_internal_end_boundaries=len(ends_a&ends_b),legacy_only_internal_end_boundaries=len(ends_a-ends_b),v2_only_internal_end_boundaries=len(ends_b-ends_a),
        differing_internal_end_boundaries=len(ends_a^ends_b),shared_exact_trimmed_payloads=shared,
        legacy_unmatched_payloads=len(legacy)-shared,v2_unmatched_payloads=len(v2)-shared,
        ordinal_payload_positions_different=sum(x!=y for x,y in zip_longest([c['text'].strip() for c in legacy],[c['text'].strip() for c in v2])))
    return stats,comparison,strategies,all_sizes


def local_reference_failures(path,text):
    failures=[]
    for match in re.finditer(r'!?\[[^\]\n]*\]\(([^)\n]+)\)',text):
        href=match[1].split('#',1)[0]
        if not href or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',href):continue
        href=unquote(href.split(' "',1)[0].strip('<>'))
        if not (path.parent/href).resolve().is_file():failures.append(dict(offset=match.start(),reference=match[1]))
    return failures


def audit_pages(out,r2):
    page_records=[];failed=[];counts=Counter()
    for unit in load(out/'source-manifest.json')['source_units']:
        if unit['family']!='prusa':continue
        sid=unit['id'];mapping=load(out/unit['source_map']);text=(out/unit['normalized_path']).read_text(encoding='utf-8')
        by_id={b['id']:b for b in mapping['source_blocks']};ranges={b['id']:b for b in mapping['records'] if b['kind']!='derived-availability'}
        representations={x['block_id']:x for x in mapping['representation_changes']}
        for page in mapping['pages']:
            p=page['page'];geometry=load(r2/'geometry'/sid/f'{p:03d}.json');blocks=[by_id[i] for i in page['source_block_ids']]
            errors=[];owners=defaultdict(list)
            def fail(kind,**detail):errors.append(dict(source_id=sid,page=p,check=kind,**detail))
            for block in blocks:
                for i in block['source_lines']:owners[i].append(block['id'])
            footers={l['index'] for l in geometry['lines'] if l['top']>geometry['height']*.92 and l['text'].strip()==str(p)}
            for line in geometry['lines']:
                i=line['index']
                if i in footers:continue
                if len(owners[i])!=1:fail('source-line-ownership',source_line=i,owners=owners[i])
            if [b['top'] for b in blocks]!=sorted(b['top'] for b in blocks):fail('block-coordinate-order')
            checked_cells=0;checked_lines=0;checked_tokens=0
            for block in blocks:
                record=ranges[block['id']];own=text[record['start']:record['end']];kind=block['kind']
                if kind=='figure':
                    if 'Visual information unavailable in text' not in own:fail('missing-visual-unavailable-marker',block=block['id'])
                    if not record['render_path'] or not (out/record['render_path']).is_file():fail('figure-reference',block=block['id'])
                    continue
                if kind=='table':
                    for cell in record['cells']:
                        value=block['source_rows'][cell['row']][cell['column']] or ''
                        actual=text[cell['start']:cell['end']]
                        if flat(value).replace('\\','')!=flat(actual).replace('\\',''):fail('table-cell-value',block=block['id'],row=cell['row'],column=cell['column'])
                        checked_cells+=1
                    source=''.join(c['text'] for i in block['source_lines'] for c in geometry['lines'][i]['chars'])
                    cells=''.join(value or '' for row in block['source_rows'] for value in row)
                    if Counter(re.sub(r'\s','',source))!=Counter(re.sub(r'\s','',cells)):fail('native-table-glyph-multiset',block=block['id'])
                else:
                    for i in block['source_lines']:
                        line=geometry['lines'][i];checked_lines+=1
                        if block.get('source_columns'):
                            # Reviewed R3B reorder: verify each original column fragment separately.
                            fragments=[''.join(c['text'] for c in sorted(line['chars'],key=lambda c:c['x0']) if (c['x0']<block['column_cut'])==side) for side in (True,False)]
                        elif block.get('rotated_source_object_text'):
                            # Full paragraph must match its hash-pinned R3B text below; native rotation is an explicit repair.
                            continue
                        else:
                            fragment=''.join(c['text'] for c in sorted(line['chars'],key=lambda c:c['x0']))
                            if kind=='menu':fragment=re.sub(r'^[❏□▢]\s*','',fragment)
                            changed=representations.get(block['id'],{})
                            if any(marker['source_line']==i for marker in changed.get('encoded_marker_replacements',[])):
                                fragment=re.sub(r'^[•●▪◦–-]\s*','',fragment)
                            fragments=[fragment]
                        for fragment in fragments:
                            if flat(fragment) and flat(fragment) not in flat(own):fail('source-line-glyph-order',block=block['id'],source_line=i)
                    if kind=='menu':
                        expected=[row['label'] for row in block['rows']]
                        if any(flat(label) not in flat(own) for label in expected):fail('menu-label',block=block['id'])
                # Check literal numeric values, units/negations/qualifiers via independent source fragments above,
                # and explicit per-block token retention. This does not certify semantic applicability.
                reference=(' '.join(row['label'] for row in block['rows']) if kind=='menu' else ' '.join(v or '' for row in block['source_rows'] for v in row) if kind=='table' else block['text'])
                needles=re.findall(r'\d+(?:[.,/]\d+)*(?:%\+?)?|\b(?:not|never|unless|only|before|nicht|niemals|nur|bevor|nie|nigdy|tylko|przed|jeśli|jeżeli)\b',reference,re.I)
                normalized=flat(own)
                for needle in needles:
                    checked_tokens+=1
                    if flat(needle) not in normalized:fail('technical-value-negation-token',block=block['id'],token=needle)
                if block.get('rotated_source_object_text') and flat(block['text']) not in flat(own):fail('rotated-repair-text',block=block['id'])
            if not (out/page['render_path']).is_file() or digest(out/page['render_path'])!=page['render_sha256']:fail('page-raster-integrity')
            if len(blocks)!=len(set(page['source_block_ids'])):fail('duplicate-source-block')
            record=dict(source_id=sid,page=p,source_blocks=len(blocks),native_lines=len(geometry['lines'])-len(footers),excluded_page_number_footers=sorted(footers),
                source_lines_checked=checked_lines,table_cells_checked=checked_cells,technical_tokens_checked=checked_tokens,source_layer=page['source_layer'],
                checks_passed=not errors,failures=errors,semantic_certification=False)
            page_records.append(record);failed.extend(errors);counts.update(lines=checked_lines,cells=checked_cells,technical_tokens=checked_tokens)
    if len(page_records)!=418:raise ValueError('Expected all 418 pages')
    return dict(pages=418,passed=sum(r['checks_passed'] for r in page_records),failed_pages=sum(not r['checks_passed'] for r in page_records),
        failed_checks=failed,checks=dict(counts),records=page_records,
        limitation='Structural consistency against pinned native object layer and reviewed repairs; inherited semantic/visual/applicability risks are not certified or cleared')


def run(out,r2):
    pages=audit_pages(out,r2);write(out/'structural-audit-418.json',pages)
    manifest=load(out/'source-manifest.json');units=[];all_sizes=defaultdict(list)
    for unit in manifest['source_units']:
        sid=unit['id'];path=out/unit['normalized_path'];text=path.read_text(encoding='utf-8')
        source_map=load(out/unit['source_map']) if unit['family']=='prusa' else None
        stats,comparison,chunks,sizes=chunk_metrics(path,text,source_map)
        references=local_reference_failures(path,text)
        for strategy in ('legacy','structure-v2'):
            all_sizes[strategy].extend(sizes[strategy])
            # Payload text stays local. Repository exports contain counts/hashes only.
            write(out/'chunk-maps'/f'{sid}-{strategy}.json',dict(source_id=sid,normalized_sha256=digest(path),strategy=strategy,records=chunks[strategy+'_joins']))
        result=dict(source_id=sid,family=unit['family'],normalized_sha256=digest(path),characters=len(text),body_characters=unit['body_characters'],
                    bytes=path.stat().st_size,chunking=stats,boundary_comparison=comparison,local_reference_failures=references)
        units.append(result)
        print(sid,stats['legacy']['chunks'],stats['structure-v2']['chunks'],'boundary differences',comparison['differing_internal_end_boundaries'],'refs',len(references),flush=True)
    summary=dict(task='3C.2A-R3C',status='candidate-only-no-admission',units=units,total_characters=sum(u['characters'] for u in units),total_body_characters=sum(u['body_characters'] for u in units),
        total_bytes=sum(u['bytes'] for u in units),chunks={s:sum(u['chunking'][s]['chunks'] for u in units) for s in ('legacy','structure-v2')},
        distributions={s:distribution(all_sizes[s]) for s in all_sizes},
        added_overlap_characters=sum(u['chunking']['legacy']['added_overlap_characters'] for u in units),
        added_v2_context_characters=sum(u['chunking']['structure-v2']['added_context_characters'] for u in units),
        resource_review_trigger_exceeded=any(sum(u['chunking'][s]['chunks'] for u in units)>3000 for s in ('legacy','structure-v2')),
        structural_failed_pages=pages['failed_pages'],local_reference_failures=sum(len(u['local_reference_failures']) for u in units),
        no_forced_identical_prusa_payloads=all(not u['boundary_comparison']['trimmed_payload_sequence_identical'] for u in units if u['family']=='prusa'))
    write(out/'chunking-comparison.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('units','distributions')},indent=2))


def representative_review(out):
    manifest=load(out/'source-manifest.json');groups=[];cache={}
    for group in load(out/'warning-applicability-reviewed.json'):
        sid=group['source_id'];u=next(u for u in manifest['source_units'] if u['id']==sid)
        mapping=load(out/u['source_map']);blocks={b['id']:b for b in mapping['source_blocks']};records={b['id']:b for b in mapping['records']}
        path=out/u['normalized_path'];text=path.read_text(encoding='utf-8');row=dict(group=group['id'],source_id=sid,source_pages=group['pages'],note_bodies=len(group['warning_source_ids']),strategies={})
        for strategy in ('legacy','structure-v2'):
            chunks,_=actual_chunks(path,text,strategy);cache[sid,strategy]=chunks
            scope=[i for i,c in enumerate(chunks) if any(c['start']<r['end'] and r['start']<c['end'] for r in group['source_ranges'])]
            notes=[]
            for bid in group['warning_source_ids']:
                b=blocks[bid];record=records[bid];a,z=record['source_text_start'],record['source_text_end']
                visible=[i for i in scope if any(x<=a and z<=y for x,y in [(chunks[i]['start'],chunks[i]['end'])]+[tuple(s) for s in chunks[i]['contexts']]) and flat(b['text']) in flat(chunks[i]['text'])]
                notes.append(dict(source_block_id=bid,page=b['page'],source_characters=z-a,wholly_visible_scope_chunk_indices=visible))
            row['strategies'][strategy]=dict(scope_chunks=len(scope),notes_whole_somewhere=sum(bool(n['wholly_visible_scope_chunk_indices']) for n in notes),note_records=notes)
        groups.append(row)
    examples=[('prusa-mk4s-en',19),('prusa-mmu3-en',40),('prusa-mk4-de',7),('prusa-xl-de',23),('prusa-mini-pl',44),('prusa-mk3s-pl',69)]
    html=['<!doctype html><meta charset="utf-8"><title>R3C representative source and actual chunks</title><style>body{font:15px system-ui;margin:2em}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1em}img{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:2px solid #888;margin-top:2em}</style><h1>Representative checks; agent origin, not semantic admission</h1>']
    for sid,p in examples:
        u=next(u for u in manifest['source_units'] if u['id']==sid);mapping=load(out/u['source_map']);page=next(pg for pg in mapping['pages'] if pg['page']==p);text=(out/u['normalized_path']).read_text(encoding='utf-8')
        html.append(f'<section><h2>{sid} / PDF page {p}</h2><div class="pair"><div><img src="{page["render_path"]}" alt="Original PDF page"></div><pre>'+escape(text[page['start']:page['end']])+'</pre></div>')
        for strategy in ('legacy','structure-v2'):
            html.append('<details><summary>'+strategy+' actual overlapping payloads</summary>')
            for index,c in enumerate(cache[sid,strategy]):
                if c['start']<page['end'] and page['start']<c['end']:html.append(f'<h3>Chunk {index}; source {c["start"]}:{c["end"]}</h3><pre>'+escape(c['text'])+'</pre>')
            html.append('</details>')
        html.append('</section>')
    (out/'representative-review.html').write_text('\n'.join(html),encoding='utf-8')
    write(out/'representative-scope-diagnostics.json',dict(scope='Source-presence diagnostics only; no questions, gold labels or retrieval results',groups=groups,
        representative_pages=[dict(source_id=s,page=p) for s,p in examples],reviewer_origin='agent',independent_human_certification=False,
        limitation='Note counts do not impose every note on every chunk. All source text remains; completeness of a payload is distinct from source validity.'))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--r2',type=Path,required=True)
    ap.add_argument('--representatives-only',action='store_true');args=ap.parse_args()
    if not args.representatives_only:run(args.output,args.r2)
    representative_review(args.output)
