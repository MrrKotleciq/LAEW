"""R2 preparation with immutable input guards and bounded dependency packets."""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import os
import subprocess

from prusa_pdf_remediation import color_kind,contains,box,page_objects,plain_line,rich_line,sha,dump,source_tables,convert_page,is_footer


CHUNK_SIZE=1000


class DependencyCapacityError(ValueError):
    """Required verbatim dependency text does not fit the unchanged chunk contract."""


def guard_inputs(corpus,r1,output,record=True):
    roots=[('accepted',corpus,'integrity-inventory.json'),('r1',r1,'r1-integrity-inventory.json')]
    snapshots={}
    for label,root,inventory_name in roots:
        inventory=json.loads((root/inventory_name).read_text(encoding='utf-8'))
        for item in inventory['files']:
            path=(root/item['path']).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file() or sha(path)!=item['sha256']:
                raise ValueError(f'Input changed: {label}/{item["path"]}')
        names=[inventory_name,'source-manifest.json' if label=='accepted' else 'review-snapshot-manifest.json']
        snapshots[label]={'files_verified':len(inventory['files']),'anchors':{name:sha(root/name) for name in names}}
        if record:
            folder=output/'input-snapshots'/label;folder.mkdir(parents=True,exist_ok=True)
            for name in names:
                target=folder/name
                if target.exists() and sha(target)!=sha(root/name):raise ValueError('R2 snapshot input identity changed')
                if not target.exists():shutil.copyfile(root/name,target)
    if record:dump(output/'input-integrity.json',snapshots)
    return snapshots


def prepare_output(corpus,r1,value):
    output=value.resolve();protected=[corpus.resolve(),r1.resolve(),Path(r'C:\ROOT')]
    if output==Path(output.anchor) or any(output.is_relative_to(p) or p.is_relative_to(output) for p in protected):
        raise ValueError('R2 workspace must be separate from accepted corpus, R1 and C:\\ROOT')
    if any((p/'.obsidian').exists() for p in (output,*output.parents)):raise ValueError('R2 must be outside vaults')
    output.mkdir(parents=True,exist_ok=True)
    return output


def packetize(source,dependencies,*,source_id,scope,limit=CHUNK_SIZE):
    """Evaluation-only Markdown repetition; never truncate or summarize dependencies.

    A unique leaf heading creates an existing-chunker boundary. A complete packet
    is bounded by the existing 1000-character contract, not a changed chunker.
    """
    prefix=('[Derived repeats]\n' if dependencies else '')+''.join(f'[{d.get("alias",d["id"])}]\n{d["text"]}\n\n' for d in dependencies)
    packets=[];pos=0
    while pos<len(source):
        heading=f'###### [R2 {source_id}:{len(packets)+1}; section {scope}]\n'
        fixed=heading+prefix+'[Source]\n'
        available=limit-len(fixed)-2
        if available<1:
            raise DependencyCapacityError(f'{source_id}: required dependency/header characters={len(fixed)+2}, limit={limit}')
        stop=min(len(source),pos+available)
        if stop<len(source):
            split=source.rfind('\n\n',pos,stop)
            if split<=pos:split=max(source.rfind(' ',pos,stop),source.rfind('\n',pos,stop))
            if split<=pos:raise DependencyCapacityError(f'{source_id}: indivisible source token exceeds remaining packet capacity')
            stop=split+1
        text=fixed+source[pos:stop]+'\n\n'
        assert len(text)<=limit
        packets.append(dict(text=text,start=pos,end=stop,dependencies=[d['id'] for d in dependencies],
            dependency_characters=len(prefix),structural_characters=len(heading)+len('[Source]\n')+2))
        pos=stop
    return packets


def heading_on_line(line):
    text=plain_line(line)
    m=re.match(r'^(\d+(?:\.\d+)*\.?)\s+\S',text)
    if not m:return None
    font=any(re.search('Bebas|Condensed|Compressed',name,re.I) for name in line['fonts'])
    bold=any('Bold' in f for f in line['fonts'])
    nested=len(m[1].rstrip('.').split('.'))>=3
    if (font and line['font_size']>=10) or (bold and (line['font_size']>=12 or nested and line['font_size']>=11)):
        return {'text':text,'number':m[1].rstrip('.')}
    return None


def preflight(corpus,r1,output):
    """Read-only geometry/capacity scan, before any full candidate conversion."""
    import pdfplumber
    notes=[];pages=[]
    dictionary=json.loads((r1/'reviewed-icon-dictionary.json').read_text(encoding='utf-8'))
    for pdf in sorted((corpus/'originals').glob('prusa-*.pdf')):
        sid=pdf.stem;scope=None
        with pdfplumber.open(pdf) as doc:
            for number,p in enumerate(doc.pages,1):
                data=page_objects(p,sid,number)
                headings=[(line['top'],heading_on_line(line)) for line in data['lines'] if heading_on_line(line)]
                start_scope=scope
                for index,shape in enumerate(data['shapes']):
                    color=color_kind(shape.get('non_stroking_color'))
                    if not shape.get('fill') or not color or shape['x1']-shape['x0']<data['width']*.4:continue
                    members=[line for line in data['lines'] if contains(box(shape),line)]
                    if not members:continue
                    preceding=[h for top,h in headings if top<shape['top']]
                    own_scope=preceding[-1] if preceding else start_scope
                    text=' '.join(plain_line(line) for line in members)
                    icon=next((im for im in data['images'] if im['width']<data['width']*.12 and abs(im['top']-shape['top'])<15 and abs(im['x0']-shape['x0'])<15),None)
                    marker=dictionary.get(icon.get('decoded_stream_sha256')) if icon else None
                    item=dict(id=f'{sid}:p{number}:box{index+1}',source_id=sid,page=number,text=text,characters=len(text),
                        scope=own_scope,bbox=box(shape),marker=marker,color='red' if color=='warning' else 'orange',
                        association='preceding source section; semantic applicability not automatically certified')
                    try:
                        packet=packetize('X',[item],source_id='capacity-probe',scope=(own_scope or {}).get('number','unresolved'))
                        item['fits_one_packet']=True;item['minimum_packet_characters']=len(packet[0]['text'])
                    except DependencyCapacityError:
                        item['fits_one_packet']=False;item['minimum_packet_characters']=len(text)+len(f'[Derived repetition; source {item["id"]}, PDF p{number}]\n')+len('###### [R2 source unit capacity-probe:1; section unresolved]\n[Source text]\nX\n\n')+2
                    notes.append(item)
                if headings:scope=headings[-1][1]
                pages.append(dict(id=sid,page=number,source_lines=len(data['lines'])))
                if number%15==0:print('Capacity preflight',sid,number,'/',len(doc.pages),flush=True)
                p.close()
        print('Preflight completed',sid,len(doc.pages),'pages',flush=True)
    groups=defaultdict(list)
    for note in notes:groups[(note['source_id'],(note['scope'] or {}).get('number'))].append(note)
    summary=dict(pages_scanned=len(pages),callouts=len(notes),individual_overflow=[n['id'] for n in notes if not n['fits_one_packet']],
        longest_individual=[{'id':n['id'],'characters':n['characters'],'scope':n['scope'],'marker':n['marker']} for n in sorted(notes,key=lambda n:-n['characters'])[:12]],
        possible_scope_capacity_risks=[{'id':sid,'scope':scope,'pages':sorted(set(n['page'] for n in group)),'combined_characters':sum(n['characters'] for n in group),'callouts':len(group)} for (sid,scope),group in groups.items() if sum(n['characters'] for n in group)>800],
        notes=notes,pages=pages,full_manual_conversion_performed=False,
        note='Scope grouping is a capacity screen, not approval that every callout applies to every descendant.')
    dump(output/'warning-capacity-preflight.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('notes','pages','possible_scope_capacity_risks')},ensure_ascii=False,indent=2),flush=True)
    return summary


def extract_full(corpus,r1,output):
    """Extend R1 with lossless fallbacks, without changing R1 or accepted files."""
    import pdfplumber
    dictionary=json.loads((r1/'reviewed-icon-dictionary.json').read_text(encoding='utf-8'))
    summary=[]
    for pdf in sorted((corpus/'originals').glob('prusa-*.pdf')):
        sid=pdf.stem;scope=None;topic=None
        with pdfplumber.open(pdf) as doc:
            for number,p in enumerate(doc.pages,1):
                data=page_objects(p,sid,number);data['icon_dictionary']=dictionary
                data['incoming_section']=scope;flags=[]
                tables,table_flags=source_tables(p);flags+=table_flags
                try:_,blocks=convert_page(data,tables)
                except ValueError as error:
                    # Preserve every glyph/line if structural inference is ambiguous; never omit text.
                    flags+=['lossless-fallback-structure-unresolved'];blocks=[]
                    for line in data['lines']:
                        if is_footer(line,data):continue
                        heading=heading_on_line(line)
                        blocks.append(dict(kind='heading' if heading else 'source-line',top=line['top'],
                            text=('#'*min(5,len(heading['number'].split('.')))+' '+heading['text']) if heading else rich_line(line),
                            source_lines=[line['index']],numbered=bool(heading),depth=min(5,len(heading['number'].split('.'))) if heading else None,
                            scope=None,fallback_reason=str(error)))
                    for i,im in enumerate(data['images'],1):
                        if im['width']*im['height']<data['width']*data['height']*.02:continue
                        blocks.append(dict(kind='figure',top=im['top'],text='',source_lines=[],bbox=box(im),image_index=i,visual_verification_required=True,scope=None))
                    blocks.sort(key=lambda b:b['top'])
                for i,b in enumerate(blocks):
                    b['id']=f'{sid}:p{number}:b{i+1}';b['page']=number;b['source_id']=sid
                    if b['kind']=='heading':
                        title=re.sub(r'^#+ ','',b['text'])
                        if b.get('numbered'):scope=title;topic=None
                        else:topic=title
                    b['scope']=scope;b['topic']=topic
                data['blocks']=blocks;data['extraction_flags']=flags;data['table_records']=tables
                dump(output/'geometry'/sid/f'{number:03d}.json',data)
                summary.append(dict(id=sid,page=number,flags=flags,blocks=len(blocks),source_lines=len(data['lines'])))
                p.close()
                if number%15==0:print('R2 extraction',sid,number,'/',len(doc.pages),flush=True)
        print('Extracted',sid,len(doc.pages),'pages',flush=True)
    if len(summary)!=418:raise ValueError('Expected 418 pages')
    dump(output/'extraction-summary.json',summary)


def dependency_policy(block):
    """Conservative candidate association, with review-required defaults.

    Reviewed exclusions preserve primary text but avoid treating warranty/image
    captions as prerequisites of unrelated technical procedures.
    """
    if block['kind'] not in ('warning','information','icon-note','callout'):return None
    text=block['text'].replace('**','')
    if re.search(r'gwarancj|warranty|Garantie|Gewährleistung',text,re.I):
        return 'warranty-primary-only'
    if re.search(r'auf diesem Foto|in (?:this|the) (?:photo|picture)|na (?:tym )?zdjęciu',text,re.I):
        return 'figure-context-only'
    if not block.get('scope'):return 'unresolved-no-broadcast'
    return 'same-source-section-and-topic-candidate'


def key_scope(block):
    value=re.match(r'\d+(?:\.\d+)*',block.get('scope') or '')
    return (value[0] if value else None,block.get('topic'))


def repair_menu_continuations(pages):
    """Reuse actual indentation levels across consecutive pages of one source section."""
    # R1 correctly rejects a page starting at an indented child without its
    # preceding parent. Recover those lossless fallback rows only when an
    # earlier explicit menu established the same source section and topic.
    established=set()
    for page in pages:
        for b in page['blocks']:
            if b['kind']=='menu':established.add(key_scope(b))
        candidates=[b for b in page['blocks'] if b['kind']=='source-line'
                    and key_scope(b) in established and re.match(r'^[❏□▢]\s*',b['text'])]
        if len(candidates)<5:continue
        grouped=defaultdict(list)
        for b in candidates:grouped[key_scope(b)].append(b)
        replacements={};removed=set()
        for group in grouped.values():
            if len(group)<5:continue
            rows=[]
            for b in group:
                index=b['source_lines'][0];line=page['lines'][index]
                rows.append(dict(label=re.sub(r'^[❏□▢]\s*','',plain_line(line)).strip(),
                                 source_line=index,bbox=box(line)))
            replacements[group[0]['id']]={**group[0],'kind':'menu','rows':rows,
                'source_lines':[r['source_line'] for r in rows],
                'r2_correction':'menu continuation recovered from lossless fallback'}
            removed.update(b['id'] for b in group[1:])
        page['blocks']=[replacements.get(b['id'],b) for b in page['blocks'] if b['id'] not in removed]
    levels=defaultdict(list);stack_by_scope={}
    for page in pages:
        for b in page['blocks']:
            if b['kind']!='menu':continue
            for row in b['rows']:
                level=page['lines'][row['source_line']]['x0']
                if not any(abs(level-x)<3 for x in levels[key_scope(b)]):levels[key_scope(b)].append(level)
    for values in levels.values():values.sort()
    for page in pages:
        for b in page['blocks']:
            if b['kind']!='menu':continue
            key=key_scope(b);stack=stack_by_scope.get(key,[]);rows=[]
            for row in b['rows']:
                x=page['lines'][row['source_line']]['x0'];depth=min(range(len(levels[key])),key=lambda n:abs(x-levels[key][n]))
                if depth>len(stack):
                    page['extraction_flags'].append('menu-parent-unresolved');depth=len(stack)
                stack=stack[:depth]+[row['label']]
                rows.append({**row,'path':' > '.join(stack),'depth':depth})
            stack_by_scope[key]=stack;b['rows']=rows
            b['text']='\n\n'.join('- Menu path: '+row['path'] for row in rows)


def repair_missed_headings(pages):
    """Split headings swallowed by R1's modal-font threshold; retain every glyph."""
    scope=None;topic=None
    for page in pages:
        repaired=[]
        for b in page['blocks']:
            if b['kind'] not in ('paragraph','source-line'):
                repaired.append(dict(b));continue
            group=[]
            def flush():
                nonlocal group
                if group:
                    repaired.append({**b,'top':group[0]['top'],'text':' '.join(rich_line(line) for line in group),'source_lines':[line['index'] for line in group]})
                    group=[]
            for index in b['source_lines']:
                line=page['lines'][index];heading=heading_on_line(line)
                if heading:
                    flush();depth=min(5,len(heading['number'].split('.')))
                    repaired.append({**b,'kind':'heading','top':line['top'],'text':'#'*depth+' '+heading['text'],
                        'source_lines':[index],'depth':depth,'numbered':True,'r2_correction':'source font/numbered subsection recovered'})
                else:group.append(line)
            flush()
        repaired.sort(key=lambda b:b['top'])
        for index,b in enumerate(repaired):
            b['id']=f'{page["id"]}:p{page["page"]}:b{index+1}'
            if b['kind']=='heading':
                title=re.sub(r'^#+ ','',b['text'])
                if b.get('numbered'):scope=title;topic=None
                else:topic=title
            b['scope']=scope;b['topic']=topic
        page['blocks']=repaired


def repair_icon_paragraphs(page):
    """Recover complete source paragraphs around R1's partial icon-note seeds."""
    lines=[line for line in page['lines'] if not is_footer(line,page)];runs=[]
    for line in lines:
        if runs:
            last=runs[-1][-1]
            continuous=abs(line['x0']-last['x0'])<3 and line['top']-last['bottom']<max(line['font_size'],last['font_size'])*.8 and not heading_on_line(line)
        else:continuous=False
        if continuous:runs[-1].append(line)
        else:runs.append([line])
    run_by_line={line['index']:run for run in runs for line in run}
    selected={}
    for b in page['blocks']:
        if b['kind']=='icon-note' and b['source_lines']:
            run=run_by_line[b['source_lines'][0]];selected[run[0]['index']]=run
    if not selected:return
    owned={line['index'] for run in selected.values() for line in run};new=[]
    for b in page['blocks']:
        if b['kind']=='icon-note':continue
        kept=[i for i in b['source_lines'] if i not in owned]
        if not b['source_lines']:new.append(b);continue
        if not kept:continue
        if kept!=b['source_lines']:
            b={**b,'source_lines':kept,'text':' '.join(rich_line(page['lines'][i]) for i in kept),'top':page['lines'][kept[0]]['top']}
        new.append(b)
    for run in selected.values():
        new.append(dict(kind='icon-note',top=run[0]['top'],text=' '.join(rich_line(line) for line in run),source_lines=[line['index'] for line in run],
            page=page['page'],source_id=page['id'],scope=None,r2_correction='complete icon-adjacent paragraph recovered from coordinate run'))
    used={i for b in new for i in b['source_lines']}
    for run in runs:
        missing=[line for line in run if line['index'] not in used]
        if missing:
            new.append(dict(kind='paragraph',top=missing[0]['top'],text=' '.join(rich_line(line) for line in missing),source_lines=[line['index'] for line in missing],
                page=page['page'],source_id=page['id'],scope=None,r2_correction='text outside the icon paragraph restored as ordinary source prose'))
    page['blocks']=sorted(new,key=lambda b:b['top'])


def reviewed_dependencies(block,blocks):
    """Materialize only reviewed source relationships, never every broad heading match."""
    sid=block['source_id'];number=key_scope(block)[0];selected=[]
    for note in blocks:
        if note['kind'] not in ('warning','information','icon-note','callout','source-condition') or note['id']==block['id']:continue
        n=key_scope(note)[0];allow=False
        if sid=='prusa-mk3s-pl':allow=number=='7.2.9' and n=='7.2.9' and note['page']==35
        elif sid=='prusa-xl-de':allow=number=='4.3' and n=='4.3' and ((note['page'] in (23,24) and note['kind']=='warning') or note['page']==23 and note['kind']=='source-condition')
        elif sid=='prusa-mmu3-en':allow=number=='2.6' and n=='2.6' and note['page']==22
        elif sid=='prusa-mini-pl':allow=number=='9.1' and n=='9.1' and note['page']==44 and dependency_policy(note)=='same-source-section-and-topic-candidate' and 'dwustronnie' not in note['text']
        elif sid=='prusa-mk4-de':allow=(number=='4.3' and n=='4.3' and note['page']==21) or (number=='4.4' and ((note['page']==21 and 'Druckblech muss' in note['text']) or (note['page']==22 and note['kind']=='warning')))
        elif sid=='prusa-mk4s-en':
            allow=(number=='4.3' and n=='4.3' and note['page']==18) or (number=='4.4' and ((note['page']==18 and note['kind']=='warning') or (note['page']==19 and note['kind']=='warning')))
        if note.get('condition_role')=='filament-length' and number=='4.4' and sid in ('prusa-mk4s-en','prusa-mk4-de'):allow=True
        if note.get('condition_role')=='finger-clearance':allow=block['id']==note['origin_block']
        if allow:selected.append(note)
    return selected


def compile_candidates(corpus,r1,output):
    manifest=json.loads((corpus/'source-manifest.json').read_text(encoding='utf-8'))
    results=[];all_relations=[];capacity=[]
    for unit in (u for u in manifest['source_units'] if u['family']=='prusa'):
        sid=unit['id'];pages=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((output/'geometry'/sid).glob('*.json'))]
        for page in pages:repair_icon_paragraphs(page)
        repair_missed_headings(pages)
        repair_menu_continuations(pages)
        for page in pages:
            dump(output/'structured'/sid/f'{page["page"]:03d}.json',{k:page[k] for k in ('id','page','blocks','extraction_flags')})
        blocks=[b for p in pages for b in p['blocks']];by_scope=defaultdict(list)
        derived=[]
        # Original bold restriction on XL p23, visually checked against the PDF.
        for b in blocks:
            if sid=='prusa-xl-de' and b['page']==23 and b['kind']=='paragraph' and '**Bevor Sie' in b['text']:
                spans=list(re.finditer(r'\*\*(.*?)\*\*',b['text']))
                restriction=' '.join(m[1] for m in spans)
                derived.append({**b,'id':b['id']+':condition','kind':'source-condition','text':restriction,
                    'origin_block':b['id'],'source_markdown_spans':[[m.start(1),m.end(1)] for m in spans],
                    'policy':'visually reviewed contiguous source bold restriction; not generated advice'})
            if sid=='prusa-xl-de' and b['page']==23 and b['kind']=='paragraph' and '**Achten Sie auf Ihre Finger!' in b['text']:
                span=next(m for m in re.finditer(r'\*\*(.*?)\*\*',b['text']) if 'Achten Sie' in m[1])
                derived.append({**b,'id':b['id']+':fingers','kind':'source-condition','text':span[1],'origin_block':b['id'],
                    'source_markdown_spans':[[span.start(1),span.end(1)]],'condition_role':'finger-clearance','policy':'reviewed source warning, only its own alignment instruction'})
            if ((sid=='prusa-mk4s-en' and b['page']==19 and b['text'].startswith('For the Selftest and')) or
                (sid=='prusa-mk4-de' and b['page']==22 and b['text'].startswith('Für den Selbsttest und'))):
                derived.append({**b,'id':b['id']+':filament','kind':'source-condition','origin_block':b['id'],
                    'source_markdown_spans':[[0,len(b['text'])]],'condition_role':'filament-length','policy':'reviewed complete source prerequisite for Selftest/filament-sensor calibration'})
        for b in blocks:
            policy=dependency_policy(b)
            if policy:
                b['dependency_policy']=policy
                if policy=='same-source-section-and-topic-candidate':by_scope[key_scope(b)].append(b)
        pieces=[];primary=[];packets=[];components=[];aliases={};alias_counts=Counter();source_headers=0;source_chars=0
        def dependency_record(d):
            if d['id'] not in aliases:
                alias_counts[d['page']]+=1;aliases[d['id']]=f'p{d["page"]}n{alias_counts[d["page"]]}'
            return dict(id=d['id'],alias=aliases[d['id']],page=d['page'],text=d['text'])
        def append(text):
            start=sum(map(len,pieces));pieces.append(text);return start,start+len(text)
        for b in blocks:
            if b['kind']=='heading':
                text=b['text']+'\n\n<!-- Derived structural boundary; source heading retained above. -->\n\n'
                a,z=append(text);primary.append(dict(block_id=b['id'],page=b['page'],start=a,end=z,kind='heading',source_lines=b['source_lines']))
                source_headers+=len(b['text']);source_chars+=len(b['text']);continue
            content=b['text']
            if b['kind']=='table':
                # R1's internal derived cell headings are data labels inside a packet, not new chunk boundaries.
                content=re.sub(r'(?m)^#{1,6} ', '[Source row/column] ',content)
            if b['kind']=='figure':
                pdf_link=os.path.relpath(corpus/unit['original_path'],output/'candidates').replace('\\','/')
                figure=f'../page-renders/{sid}/page-{b["page"]:03d}.png'
                content=f'[Visual verification required; original PDF p{b["page"]}; figure bbox {b.get("bbox")}]\n![Original PDF page {b["page"]}]({figure})\n[Original PDF]({pdf_link}#page={b["page"]})'
            # Protect literal source '#' lines against legacy's heading regex (also inside code).
            content=re.sub(r'(?m)^(#{1,6})\s',lambda m:'[Literal source hash] '+m[1]+' ',content)
            candidates=[d for d in by_scope[key_scope(b)] if d['id']!=b['id']]
            deps=reviewed_dependencies(b,blocks+derived)
            if b['kind']=='figure':deps=[]  # Visual-only references are not asserted to be executable instructions.
            # A source note always remains a primary record; semantic exclusions only affect repetition.
            if b.get('dependency_policy') in ('warranty-primary-only','figure-context-only','unresolved-no-broadcast'):deps=[]
            parts=[dict(id=b['id'],text=content,context=None)]
            if b['kind']=='table':
                parts=[]
                for row_index,row in enumerate(b['source_rows']):
                    for col_index,value in enumerate(row):
                        if not value:continue
                        context=None
                        if row_index:
                            row_name=row[0].replace('\n',' ')
                            col_name=b['source_rows'][0][col_index].replace('\n',' ') if b['header_verified'] else f'column {col_index+1}'
                            context=dict(id=b['id']+f':r{row_index+1}c{col_index+1}:context',page=b['page'],source_id=sid,
                                text=f'[Source table row/column] {row_name} / {col_name}',kind='table-context',origin_block=b['id'],row=row_index,column=col_index,
                                policy='derived juxtaposition of verbatim source table labels')
                            derived.append(context)
                        parts.append(dict(id=b['id']+f':r{row_index+1}c{col_index+1}',text=value.replace('\n',' '),context=context))
            for component in parts:
                dep_records=[dependency_record(d) for d in deps]
                if component['context']:dep_records.append(dependency_record(component['context']))
                try:created=packetize(component['text'],dep_records,source_id=component['id'].split(':',1)[1],scope=key_scope(b)[0] or 'unresolved')
                except DependencyCapacityError as error:
                    capacity.append(dict(id=sid,page=b['page'],block=b['id'],dependencies=[d['id'] for d in deps],error=str(error)))
                    dump(output/'contract-stop.json',{'reason':'Reviewed dependency set exceeds unchanged chunk contract','cases':capacity,'full_manual_conversion_completed':False})
                    raise
                source_chars+=len(component['text']);components.append({**component,'context':component['context']['id'] if component['context'] else None,'block_id':b['id'],'page':b['page']})
                for packet in created:
                    a,z=append(packet['text']);packet.update(start_in_document=a,end_in_document=z,page=b['page'],block_id=b['id'],component_id=component['id'],kind=b['kind'])
                    primary.append(dict(block_id=b['id'],component_id=component['id'],page=b['page'],start=a,end=z,kind=b['kind'],source_start=packet['start'],source_end=packet['end'],source_lines=b['source_lines']))
                    packets.append(packet)
            all_relations.append(dict(id=b['id'],source_id=sid,page=b['page'],kind=b['kind'],scope=b['scope'],topic=b.get('topic'),
                dependencies=[d['id'] for d in deps],candidate_dependencies_not_materialized=[d['id'] for d in candidates if d['id'] not in {note['id'] for note in deps}],
                policy=b.get('dependency_policy'),applicability_status='reviewed-rule' if deps else 'requires-review' if candidates else 'no-materialized-dependency',source_lines=b['source_lines']))
        body=''.join(pieces)
        path=output/'candidates'/f'{sid}.md';path.parent.mkdir(exist_ok=True);path.write_text(body,encoding='utf-8')
        dump(output/'maps'/f'{sid}.json',dict(primary=primary,packets=packets,components=components,derived_dependencies=derived,dependency_aliases=aliases,pages=[{'page':p['page'],'flags':p['extraction_flags']} for p in pages],
            source_pdf_sha256=unit['original_sha256'],source_headers_characters=source_headers,primary_representation_characters=source_chars))
        results.append(dict(id=sid,pages=len(pages),candidate_path=f'candidates/{sid}.md',characters=len(body),bytes=path.stat().st_size,
            sha256=sha(path),packets=len(packets),primary_representation_characters=source_chars,
            dependency_repetition_characters=sum(p['dependency_characters'] for p in packets),derived_packet_structure_characters=sum(p['structural_characters'] for p in packets)))
        print('Candidate compiled',sid,len(body),'characters',len(packets),'packets',flush=True)
    dump(output/'candidate-results.json',results);dump(output/'dependency-relations.json',all_relations)
    dump(output/'contract-status.json',{'reviewed_dependency_sets_fit_unchanged_contract':True,
        'unreviewed_broad_associations_materialized':False,'earlier_stops':'Broad/incorrect section grouping; retained diagnostics do not establish a required production-contract change.'})


def render_pages(corpus,output):
    renderer=shutil.which('pdftoppm')
    if not renderer:raise RuntimeError('Bundled pdftoppm is required')
    for pdf in sorted((corpus/'originals').glob('prusa-*.pdf')):
        target=output/'page-renders'/pdf.stem;target.mkdir(parents=True,exist_ok=True)
        expected=next(u['page_count'] for u in json.loads((corpus/'source-manifest.json').read_text(encoding='utf-8'))['source_units'] if u['id']==pdf.stem)
        if len(list(target.glob('page-*.png')))==expected:continue
        subprocess.run([renderer,'-scale-to','1400','-png',str(pdf),str(target/'page')],check=True)
        # Poppler pads page numbers to the document's width, normalize to three digits.
        for path in list(target.glob('page-*.png')):
            number=int(path.stem.rsplit('-',1)[-1]);new=target/f'page-{number:03d}.png'
            if new!=path:path.rename(new)
        print('Rendered',pdf.stem,expected,'original pages',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--r1',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--preflight',action='store_true');ap.add_argument('--extract',action='store_true')
    ap.add_argument('--compile',action='store_true');ap.add_argument('--render',action='store_true');args=ap.parse_args()
    output=prepare_output(args.corpus,args.r1,args.output);guard_inputs(args.corpus,args.r1,output)
    if args.preflight:preflight(args.corpus,args.r1,output)
    if args.extract:extract_full(args.corpus,args.r1,output)
    if args.compile:compile_candidates(args.corpus,args.r1,output)
    if args.render:render_pages(args.corpus,output)
    guard_inputs(args.corpus,args.r1,output)
