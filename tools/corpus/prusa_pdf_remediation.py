"""R1-only geometry inspection and sample conversion. Never replaces corpus files."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys


SAMPLES = [('prusa-mk3s-pl',35),('prusa-xl-de',23),('prusa-mk4s-en',42),
           ('prusa-mk4-de',43),('prusa-mini-pl',31),('prusa-mmu3-en',22),
           ('prusa-xl-de',7),('prusa-xl-de',46)]
# Literal icon glyphs read from rendered source samples, not inferred from fill color.
REVIEWED_MARKERS={('prusa-mk3s-pl',35):['i'],('prusa-xl-de',23):['!','!'],
                  ('prusa-mmu3-en',22):['i'],('prusa-mini-pl',44):['!','!','i','i']}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def output_root(corpus, output):
    corpus=corpus.resolve(strict=True);output=output.resolve()
    if output.is_relative_to(corpus) or corpus.is_relative_to(output):
        raise ValueError('R1 output must be separate from the accepted corpus')
    if output==Path(output.anchor) or output.is_relative_to(Path(r'C:\ROOT')):
        raise ValueError('R1 artifacts must be outside C:\\ROOT')
    if any((p/'.obsidian').exists() for p in (output,*output.parents)):
        raise ValueError('R1 output must not be in an Obsidian vault')
    output.mkdir(parents=True,exist_ok=True)
    return output


def baseline_guard(corpus,output,*,record=True):
    """Snapshot existing trust anchors without modifying them or their inventory."""
    anchors={name:sha(corpus/name) for name in ('source-manifest.json','integrity-inventory.json')}
    target=output/'baseline-snapshot'
    if record:target.mkdir(exist_ok=True)
    elif not target.is_dir():raise ValueError('Missing archived baseline trust anchors')
    for name,digest in anchors.items():
        archived=target/name
        if archived.exists() and sha(archived)!=digest:raise ValueError('Baseline changed since R1 began')
        if not archived.exists():
            if not record:raise ValueError('Missing archived baseline trust anchor')
            shutil.copyfile(corpus/name,archived)
    inventory=json.loads((corpus/'integrity-inventory.json').read_text(encoding='utf-8'))
    for item in inventory['files']:
        if sha(corpus/item['path'])!=item['sha256']:raise ValueError('Accepted corpus hash mismatch: '+item['path'])
    guard=dict(anchors=anchors,files_checked=len(inventory['files']),unchanged=True,
        wal_commit=next(u['commit'] for u in json.loads((corpus/'source-manifest.json').read_text(encoding='utf-8'))['source_units'] if u['id']=='postgresql-17-runtime-config-wal'))
    if record:dump(output/'baseline-guard.json',guard)
    elif json.loads((output/'baseline-guard.json').read_text(encoding='utf-8'))!=guard:raise ValueError('Baseline guard changed')
    return anchors


def color_kind(value):
    if not isinstance(value,(list,tuple)) or len(value)!=3:return None
    r,g,b=value
    if r>.65 and g<.25 and b<.3:return 'warning'
    if r>.65 and .25<=g<.65 and b<.3:return 'information'
    return None


def box(obj):
    return [obj[k] for k in ('x0','top','x1','bottom')]


def contains(b,line):
    return b[0]-1<=line['x0'] and line['x1']<=b[2]+1 and b[1]-1<=line['top'] and line['bottom']<=b[3]+1


def word_counts(text):
    return Counter(re.findall(r'\w+',text.casefold()))


def is_footer(line,page):
    return line['top']>page['height']*.92 and line['text'].strip()==str(page['page'])


def rich_line(line):
    """Retain glyphs and explicit bold runs; infer spaces only from glyph gaps."""
    segments=[];active=False;previous=None;buffer=''
    for c in sorted(line['chars'],key=lambda c:c['x0']):
        bold=bool(re.search(r'bold|black|heavy|medium',c['fontname'],re.I))
        gap=previous is not None and c['x0']-previous['x1']>min(c['size'],previous['size'])*.12
        if gap and buffer and not buffer.endswith(' '):buffer+=' '
        if bold!=active:
            segments.append((active,buffer));buffer='';active=bold
        buffer+=c['text'];previous=c
    segments.append((active,buffer));result=[]
    for bold,value in segments:
        core=value.strip()
        if bold and core:
            leading=value[:len(value)-len(value.lstrip())];trailing=value[len(value.rstrip()):]
            result.append(leading+'**'+core+'**'+trailing)
        else:result.append(value)
    return ''.join(result).strip()


def plain_line(line):
    return rich_line(line).replace('**','')


def page_objects(p,sid,number):
    lines=[]
    for i,line in enumerate(p.extract_text_lines(x_tolerance=1,y_tolerance=2,return_chars=True)):
        chars=line.pop('chars')
        line.update(index=i,font_size=max((c['size'] for c in chars),default=0),
            fonts=sorted(set(c['fontname'] for c in chars)),
            chars=[{k:c.get(k) for k in ('text','x0','x1','top','bottom','size','fontname','non_stroking_color')} for c in chars])
        lines.append(line)
    shapes=[{k:r.get(k) for k in ('object_type','x0','x1','top','bottom','fill','stroke','non_stroking_color','stroking_color','linewidth')} for r in p.rects+p.curves]
    images=[]
    for im in p.images:
        record={k:im.get(k) for k in ('x0','x1','top','bottom','width','height','name','srcsize')}
        if im['width']<p.width*.12 and im['height']<p.height*.08:
            record['decoded_stream_sha256']=hashlib.sha256(im['stream'].get_data()).hexdigest()
        images.append(record)
    return dict(id=sid,page=number,width=p.width,height=p.height,lines=lines,shapes=shapes,images=images)


def menu_rows(lines):
    """Explicit square-bullet items only; indentation must form stable levels."""
    items=[l for l in lines if re.match(r'^[❏□▢]\s*',plain_line(l))]
    levels=[]
    for value in sorted(l['x0'] for l in items):
        if not levels or value-levels[-1]>3:levels.append(value)
    if len(items)<5 or len(levels)<2:return []
    stack=[];rows=[]
    for item in items:
        depth=min(range(len(levels)),key=lambda n:abs(item['x0']-levels[n]))
        if depth>len(stack):raise ValueError('Ambiguous menu indentation jump')
        label=re.sub(r'^[❏□▢]\s*','',plain_line(item)).strip()
        stack=stack[:depth];stack.append((label,item['index']))
        rows.append(dict(label=label,depth=depth,path=' > '.join(x[0] for x in stack),
            source_line=item['index'],ancestor_lines=[x[1] for x in stack[:-1]],bbox=box(item)))
    return rows


def source_tables(p):
    """Conservative ruled-table detector: no borderless layout guessing."""
    if len(p.edges)>1000:return [],['complex-vector-grid']
    results=[];flags=[]
    for t in p.find_tables():
        rows=t.extract(x_tolerance=1,y_tolerance=2)
        if len(rows)<2 or max((len(r) for r in rows),default=0)<2:continue
        if t.bbox[2]-t.bbox[0]<p.width*.25:continue
        merged=any(cell is None for row in t.rows for cell in row.cells)
        if merged:
            flags.append('merged-or-ambiguous-table-cells');continue
        first=t.rows[0]
        top=min(c[1] for c in first.cells);bottom=max(c[3] for c in first.cells)
        header_chars=[c for c in p.chars if top<=c['top'] and c['bottom']<=bottom and t.bbox[0]<=c['x0']<t.bbox[2] and c['text'].strip()]
        weight=sum(bool(re.search('Bold|Medium|Heavy',c['fontname'],re.I)) for c in header_chars)/max(1,len(header_chars))
        results.append(dict(bbox=list(t.bbox),rows=rows,header_verified=weight>.7,header_bold_fraction=weight))
    return results,flags


def convert_page(data,tables):
    """Return sample Markdown and source-coordinate structural map, without OCR."""
    lines=[l for l in data['lines'] if not is_footer(l,data)]
    size_counts=Counter(round(c['size'],1) for l in lines for c in l['chars'] if c['text'].strip())
    body_font=size_counts.most_common(1)[0][0] if size_counts else 0
    claimed=set();blocks=[];section=None;section_depth=1
    by_index={l['index']:l for l in lines}
    menu=menu_rows(lines)
    for table in tables:
        members=[l for l in lines if contains(table['bbox'],l)]
        if not members:continue
        rows=table['rows'];width=max(map(len,rows))
        if max(sum(len(c or '') for c in row) for row in rows)>650 and table['header_verified']:
            # Long cells cannot fit a chunk. Keep each original cell with explicit source row/column labels.
            header=rows[0];md=['<!-- Long table serialized as source-labelled cells; original matrix retained in sidecar. -->']
            for row in rows[1:]:
                for col,cell in enumerate(row[1:],1):
                    label=' / '.join([row[0].replace('\n',' '),header[col].replace('\n',' ')])
                    content=(cell or '').replace('\n',' ')
                    content=re.sub(r'\s*•\s*','\n- ',content).lstrip('\n')
                    md+=['#### '+label,content,'']
            render_kind='source-labelled-cells'
        else:
            header=rows[0] if table['header_verified'] else ['']*width
            md=['| '+' | '.join(header)+' |','| '+' | '.join(['---']*width)+' |']
            md+=['| '+' | '.join((str(c or '').replace('|',r'\|').replace('\n','<br>')) for c in row)+' |' for row in (rows[1:] if table['header_verified'] else rows)]
            render_kind='markdown-matrix'
        blocks.append(dict(kind='table',top=table['bbox'][1],text='\n'.join(md),source_lines=[l['index'] for l in members],bbox=table['bbox'],scope=None,render_kind=render_kind,source_rows=rows,header_verified=table['header_verified']))
        claimed.update(l['index'] for l in members)
    if menu:
        first=by_index[menu[0]['source_line']]
        md=['<!-- Structural menu paths: ancestor labels repeat verbatim from source indentation. -->']
        md += [f'- **Menu path:** {r["path"]}\n' for r in menu]
        blocks.append(dict(kind='menu',top=first['top'],text='\n'.join(md),source_lines=[r['source_line'] for r in menu],rows=menu,scope=None))
        claimed.update(r['source_line'] for r in menu)
    for shape in data['shapes']:
        color=color_kind(shape.get('non_stroking_color'))
        if not shape.get('fill') or not color or shape['x1']-shape['x0']<data['width']*.4:continue
        icon=next((im for im in data['images'] if im['width']<data['width']*.12 and abs(im['top']-shape['top'])<15 and abs(im['x0']-shape['x0'])<15),None)
        marker=data.get('icon_dictionary',{}).get(icon.get('decoded_stream_sha256')) if icon else None
        kind={'!':'warning','i':'information'}.get(marker,'callout')
        members=[l for l in lines if l['index'] not in claimed and contains(box(shape),l)]
        if not members:continue
        blocks.append(dict(kind=kind,top=shape['top'],text=' '.join(rich_line(l) for l in members),
            source_lines=[l['index'] for l in members],bbox=box(shape),scope=None,marker=marker,
            box_color='red' if color=='warning' else 'orange',marker_verification='reviewed exact image-stream hash' if marker else 'visual verification required'))
        claimed.update(l['index'] for l in members)
    # Icons have no text semantics inferred. Their nearest adjacent text is mapped as a note,
    # without assigning a warning level from an unrecognized icon.
    for im in data['images']:
        if im['width']>data['width']*.12 or im['height']>data['height']*.08:continue
        members=[l for l in lines if l['index'] not in claimed and l['x0']>im['x1']-1 and abs(l['top']-im['top'])<im['height']*1.2]
        if not members:continue
        last=members[-1]
        following=[l for l in lines if l['index'] not in claimed and l['top']>last['top'] and l['top']-last['bottom']<im['height']*2 and abs(l['x0']-members[0]['x0'])<3]
        members+=following
        blocks.append(dict(kind='icon-note',top=members[0]['top'],text=' '.join(rich_line(l) for l in members),source_lines=[l['index'] for l in members],scope=None))
        claimed.update(l['index'] for l in members)
    current=None
    for line in lines:
        if line['index'] in claimed:current=None;continue
        plain=plain_line(line);text=rich_line(line)
        numbered=re.match(r'^(\d+(?:\.\d+)+\.?|\d+\.)\s+(.+)',plain)
        heading_font=any(re.search('Bebas|Condensed|Compressed',f,re.I) for f in line['fonts'])
        heading=(heading_font and line['font_size']>=body_font*1.18) or (numbered and line['font_size']>=body_font*1.18 and any('Bold' in f for f in line['fonts']))
        if heading:
            depth=min(6,len(re.findall(r'\d+',numbered[1]))) if numbered else 3
            block=dict(kind='heading',top=line['top'],text='#'*depth+' '+plain,source_lines=[line['index']],depth=depth,numbered=bool(numbered),scope=None)
            blocks.append(block);current=None;continue
        list_start=bool(re.match(r'^\d+\.\s',plain))
        # Preserve caption font and numbered-step starts instead of merging them into preceding prose.
        caption=all(re.search('Italic|Oblique',f,re.I) for f in line['fonts']) and len(plain)<100 and any(0<line['top']-im['bottom']<35 and abs((line['x0']+line['x1'])/2-data['width']/2)<data['width']*.1 for im in data['images'])
        if current and not list_start and not caption and line['top']-current['last_bottom']<line['font_size']*.7:
            current['text']+=' '+text;current['source_lines'].append(line['index']);current['last_bottom']=line['bottom']
        else:
            current=dict(kind='caption' if caption else 'step' if list_start else 'paragraph',top=line['top'],text=text,source_lines=[line['index']],last_bottom=line['bottom'],scope=None)
            blocks.append(current)
    # Only substantial images become figures. Tiny icon images remain associated with callouts.
    for i,im in enumerate(data['images'],1):
        if im['width']*im['height']<data['width']*data['height']*.02:continue
        blocks.append(dict(kind='figure',top=im['top'],bbox=box(im),text=f'![Original PDF figure, page {data["page"]}](../figures/{data["id"]}-page-{data["page"]}-figure-{i}.png)',
            source_lines=[],scope=None,image_index=i,visual_verification_required=True))
    blocks.sort(key=lambda b:b['top'])
    output=[f'<!-- Original PDF page {data["page"]}; R1 derivative, not admitted corpus. -->\n']
    scope=data.get('incoming_section');used=[]
    if scope and (not blocks or blocks[0]['kind']!='heading'):
        depth=min(6,len(re.findall(r'\d+',scope.split(' ',1)[0])))
        output.append('#'*max(1,depth)+' [PDF section continued] '+scope+'\n\n')
    for block in blocks:
        if block['kind']=='heading' and block['numbered']:scope=re.sub(r'^#+ ','',block['text'])
        block['scope']=scope
        if block['kind']=='caption':
            figures=[b for b in blocks if b['kind']=='figure' and b['top']<block['top']]
            block['figure_source_page']=data['page'] if figures else None
        prefix=''
        if block['kind'] in ('warning','information','icon-note','callout'):
            name=('PDF note; icon unclassified' if block['kind']=='icon-note' else
                  block['kind'].upper()+f'; {block["box_color"]}, {block["marker"] or "unverified"}')
            scope_number=re.match(r'\d+(?:\.\d+)*',scope or '')
            prefix=f'> **[{name}; p{data["page"]}; section {scope_number[0] if scope_number else "unresolved"}]**\n> '
        elif block['kind']=='figure':
            prefix=f'**[Visual verification required; original page {data["page"]}; section {scope or "unresolved"}]**\n\n'
        elif re.search(r'im Bild|Bild oben|shown (above|below)|picture (above|below)|na (zdjęciu|obrazku)',block['text'],re.I):
            block['visual_verification_required']=True
            prefix=f'**[Visual verification required: source text refers to a figure; original page {data["page"]}]**\n\n'
        block['start']=sum(len(x) for x in output)
        output.append(prefix+block['text']+'\n\n');block['end']=sum(len(x) for x in output)
        used+=block['source_lines']
    expected={l['index'] for l in lines}
    if set(used)!=expected or len(used)!=len(set(used)):
        raise ValueError(f'Incomplete/duplicate line assignment: {expected-set(used)}')
    if not lines:output.append('<!-- No text, image, or drawing objects: original page is blank. -->\n')
    return ''.join(output),blocks


def samples(corpus,output,table_probes=False):
    import pdfplumber
    from PIL import Image
    results=[]
    cases=[('prusa-mmu3-en',40),('prusa-mini-pl',44)] if table_probes else SAMPLES
    dictionary_path=output/'reviewed-icon-dictionary.json'
    dictionary=json.loads(dictionary_path.read_text(encoding='utf-8')) if dictionary_path.exists() else {}
    for sid,number in cases:
        cache=json.loads((corpus/'extraction'/f'{sid}.json').read_text(encoding='utf-8'))
        with pdfplumber.open(corpus/'originals'/f'{sid}.pdf') as doc:
            p=doc.pages[number-1];data=page_objects(p,sid,number);tables,table_flags=source_tables(p)
            icons=sorted((im for im in data['images'] if 'decoded_stream_sha256' in im),key=lambda im:im['top'])
            reviewed=REVIEWED_MARKERS.get((sid,number),[])
            if reviewed and len(reviewed)!=len(icons):raise ValueError('Reviewed icon count changed')
            for icon,marker in zip(icons,reviewed):
                if dictionary.get(icon['decoded_stream_sha256'],marker)!=marker:raise ValueError('Conflicting icon review')
                dictionary[icon['decoded_stream_sha256']]=marker
            data['icon_dictionary']=dictionary.copy()
            prior=[]
            for old in cache['page_records'][:number-1]:
                for line in old['lines']:
                    if re.match(r'^\d+(?:\.\d+)*\.?\s+\S',line['text']) and (any(re.search('Bebas|Condensed|Compressed',font,re.I) for font in line['fonts']) and line['max_font_size']>=10 or line['max_font_size']>=12 and any('Bold' in f for f in line['fonts'])):
                        prior.append(dict(text=line['text'],page=old['page']))
            data['incoming_section']=prior[-1]['text'] if prior else None
            data['incoming_section_source_page']=prior[-1]['page'] if prior else None
            dump(output/'objects'/f'{sid}-page-{number}.json',data)
            md,blocks=convert_page(data,tables)
        original=cache['page_records'][number-1]
        mapdata=json.loads((corpus/'maps'/f'{sid}.json').read_text(encoding='utf-8'))['records'][number-1]
        old=(corpus/'normalized'/f'{sid}.md').read_text(encoding='utf-8')
        body=re.sub(r'\A---\n.*?\n---\n','',old,count=1,flags=re.S)
        before=body[mapdata['start']:mapdata['end']]
        for directory,text in [('before',before),('samples',md)]:
            target=output/directory/f'{sid}-page-{number}.md';target.parent.mkdir(exist_ok=True);target.write_text(text,encoding='utf-8')
        source_png=corpus/'verification/pdf-qa'/f'{sid}-page-{number}.png'
        (output/'renders').mkdir(exist_ok=True)
        if source_png.exists():shutil.copyfile(source_png,output/'renders'/source_png.name)
        else:
            import subprocess
            renderer=shutil.which('pdftoppm')
            if not renderer:raise RuntimeError('pdftoppm is required for sample visual QA')
            prefix=output/'renders'/f'{sid}-page-{number}'
            subprocess.run([renderer,'-f',str(number),'-l',str(number),'-singlefile','-scale-to','1700','-png',str(corpus/'originals'/f'{sid}.pdf'),str(prefix)],check=True)
            source_png=prefix.with_suffix('.png')
        for b in blocks:
            if b['kind']!='figure':continue
            with Image.open(source_png) as img:
                x0,top,x1,bottom=b['bbox'];crop=img.crop((int(x0/data['width']*img.width),int(top/data['height']*img.height),int(x1/data['width']*img.width),int(bottom/data['height']*img.height)))
                target=output/'figures'/f'{sid}-page-{number}-figure-{b["image_index"]}.png';target.parent.mkdir(exist_ok=True);crop.save(target)
        dump(output/'maps'/f'{sid}-page-{number}.json',dict(coordinates='Unicode character offsets in sample Markdown; PDF coordinates use top-origin points',blocks=blocks,
            source_pdf_sha256=sha(corpus/'originals'/f'{sid}.pdf'),tables=table_flags,removed_footer_lines=[l['text'] for l in data['lines'] if is_footer(l,data)]))
        results.append(dict(id=sid,page=number,before_characters=len(before),after_characters=len(md),
            blocks=dict(Counter(b['kind'] for b in blocks)),source_line_count=len(data['lines']),
            assigned_source_lines=sum(len(b['source_lines']) for b in blocks),
            removed_footer_count=sum(is_footer(l,data) for l in data['lines']),
            sha256=hashlib.sha256(md.encode()).hexdigest(),table_flags=table_flags,
            remaining_visual_dependencies=any(b['kind']=='figure' for b in blocks)))
        print('Converted sample',sid,number,results[-1]['blocks'],flush=True)
    dump(output/('table-probe-results.json' if table_probes else 'sample-results.json'),results)
    dump(dictionary_path,dictionary)


def audit_pages(corpus,output):
    """Read-only structural object scan; deliberately does not convert 418 pages."""
    import pdfplumber
    records=[]
    for source in sorted((corpus/'originals').glob('prusa-*.pdf')):
        sid=source.stem;cached=json.loads((corpus/'extraction'/f'{sid}.json').read_text(encoding='utf-8'))
        with pdfplumber.open(source) as doc:
            for number,p in enumerate(doc.pages,1):
                previous=cached['page_records'][number-1];flags=[]
                chars=p.chars;area=p.width*p.height
                big_images=[im for im in p.images if im['width']*im['height']>area*.02]
                colored=[r for r in p.rects if r.get('fill') and color_kind(r.get('non_stroking_color')) and r['x1']-r['x0']>p.width*.4]
                menus=[l for l in previous['lines'] if re.match(r'^[❏□▢]',l['text'])]
                tables,tableflags=source_tables(p)
                if big_images:flags.append('substantial-image-visual-review')
                if colored:flags.append('colored-callout-scope-review')
                if len(menus)>=5:flags.append('menu-indentation-review')
                if tables:flags.append('ruled-table-cell-review')
                flags+=tableflags
                # PDF text positioned as two or more columns without explicit ruling.
                aligned=sum(bool(re.search(r'\S\s{3,}\S',line)) for line in previous['layout'].splitlines())
                if aligned>=4:flags.append('alignment-or-borderless-table-review')
                if chars and previous['token_agreement']<.95:flags.append('independent-text-disagreement')
                if any(not c.get('upright',True) for c in chars):flags.append('rotated-text-review')
                if any('\ufffd' in c['text'] or '(cid:' in c['text'] for c in chars):flags.append('unmapped-glyph-review')
                if not chars and (p.images or p.rects or p.curves):flags.append('non-text-page-visual-review')
                if len(chars)<50 and big_images:flags.append('sparse-text-with-image')
                blank=not chars and not p.images and not p.rects and not p.curves and not p.lines
                record=dict(id=sid,page=number,text_characters=len(chars),image_count=len(p.images),large_images=len(big_images),
                    colored_callouts=len(colored),menu_items=len(menus),ruled_tables=len(tables),aligned_rows=aligned,
                    independent_token_agreement=previous['token_agreement'],blank_object_page=blank,flags=sorted(set(flags)),
                    inspection_status='requires-inspection' if flags else 'blank-object-page' if blank else 'no-rule-triggered-not-certified')
                records.append(record)
                if tables:dump(output/'table-candidates'/f'{sid}-page-{number}.json',tables)
                if number%15==0:print('Object audit',sid,number,'/',len(doc.pages),flush=True)
                p.close()
        print('Audited',sid,len(cached['page_records']),'pages',flush=True)
    summary=dict(pages=len(records),flagged_pages=sum(bool(r['flags']) for r in records),
        blank_pages=[{'id':r['id'],'page':r['page']} for r in records if r['blank_object_page']],
        flag_counts=dict(Counter(f for r in records for f in r['flags'])),
        note='Screening queue, not admission certification; only eight sample pages converted. No OCR.',records=records)
    if len(records)!=418:raise ValueError('Expected all 418 original pages')
    dump(output/'structural-audit-418.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2),flush=True)


def inspect(corpus,output):
    import pdfplumber
    for sid,number in SAMPLES:
        with pdfplumber.open(corpus/'originals'/f'{sid}.pdf') as doc:
            p=doc.pages[number-1]
            lines=[]
            for line in p.extract_text_lines(return_chars=True):
                chars=line.pop('chars')
                line.update(font_size=max((c['size'] for c in chars),default=0),
                    fonts=sorted(set(c['fontname'] for c in chars)),
                    chars=[{k:c.get(k) for k in ('text','x0','x1','top','bottom','size','fontname','non_stroking_color')} for c in chars])
                lines.append(line)
            shapes=[{k:r.get(k) for k in ('object_type','x0','x1','top','bottom','fill','stroke','non_stroking_color','stroking_color','linewidth')} for r in p.rects+p.curves]
            images=[{k:im.get(k) for k in ('x0','x1','top','bottom','width','height','name','srcsize')} for im in p.images]
            data=dict(id=sid,page=number,width=p.width,height=p.height,lines=lines,shapes=shapes,images=images)
            dump(output/'inspection-objects'/f'{sid}-page-{number}.json',data)
            print(sid,number,'lines',len(lines),'shapes',len(shapes),'images',len(images))
            if sid=='prusa-mk3s-pl':
                for l in lines[:22]:print(round(l['x0'],1),round(l['top'],1),round(l['font_size'],1),repr(l['text']))
            if (sid,number) in [('prusa-xl-de',23),('prusa-mmu3-en',22)]:
                print('colored shapes',[r for r in shapes if r.get('fill') and r.get('non_stroking_color') not in (None,0,[0],[1],[0,0,0],[1,1,1]) and (r['x1']-r['x0'])*(r['bottom']-r['top'])>500])
    print('PDF engine:',pdfplumber.__version__,flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--inspect',action='store_true')
    ap.add_argument('--samples',action='store_true')
    ap.add_argument('--audit-pages',action='store_true')
    ap.add_argument('--table-probes',action='store_true',help='Two additional real table pages only, not full manuals')
    args=ap.parse_args();output=output_root(args.corpus,args.output)
    baseline_guard(args.corpus,output)
    if args.inspect:inspect(args.corpus,output)
    if args.samples:samples(args.corpus,output)
    if args.table_probes:samples(args.corpus,output,table_probes=True)
    if args.audit_pages:audit_pages(args.corpus,output)
    baseline_guard(args.corpus,output)


if __name__=='__main__':main()
