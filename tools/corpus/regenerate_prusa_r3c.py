"""Hash-gated, source-once candidate corpus assembly; no admission or indexing."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from review_prusa_r3a import natural,load,write,digest
from triage_prusa_r3b import verify_triage
from prusa_pdf_remediation import rich_line

R3B_SHA='e19abd2bf1407fff11f87e2ffe4fee9a1632905ad11852a9c1b21e6a6e714bdd'
WAL_COMMIT='220b5263dbb71bbe2966c6d47c0c456c14ed4e48'


def record_origins(record,block,document):
    """Identify derived subranges so layout/availability text is not publisher prose."""
    record['contains_publisher_text']=block['kind']!='figure'
    record.pop('publisher_text',None)
    a,z=record['start'],record['end'];segments=[]
    if block['kind']=='figure':segments=[dict(start=a,end=z,kind='derived-visual-unavailability-and-source-references')]
    else:
        segments=[dict(start=a+m.start(),end=a+m.end(),kind='derived-layout-availability') for m in re.finditer(r'\[Derived layout:[^\]]*\]',document[a:z])]
        if block.get('derived_empty_header'):
            end=document.find('\n',document.find('\n',a)+1)+1
            segments.append(dict(start=a,end=end,kind='derived-neutral-empty-table-header'))
    record['derived_segments']=segments
    record['text_origin']='mixed-source-and-derived' if segments else 'source-with-Markdown-structure'
    return record


def verify_inputs(accepted,r2,r3a,r3b):
    if accepted.resolve()!=r2.parent/'stage-2b2-real-world-20261111':raise ValueError('Unexpected accepted root')
    return verify_triage(r2,r3a,r3b,R3B_SHA)


def patch_identity(unit,original_sha,structured_sha,patch):
    if original_sha!=unit['original_sha256'] or original_sha!=patch['source_pdf_sha256']:
        raise ValueError('Repair source PDF identity mismatch')
    if structured_sha!=patch['source_structured_sha256']:raise ValueError('Repair structured source identity mismatch')


def list_presentation(block,geometry):
    """Recover explicit native list starts, independent of chunk size/strategy.

    Ambiguous multi-column text is not reconstructed. Small repeated filled
    marks immediately left of text are structural bullet objects, not technical
    image descriptions. Every word and original explicit bullet remains.
    """
    if block['kind'] not in ('paragraph','source-line') or block.get('source_columns'):return block,None
    lines=[geometry['lines'][i] for i in block['source_lines']]
    if len(lines)<2:return block,None
    starts=[];vector=[]
    for line in lines:
        plain=line['text'].strip()
        explicit=bool(re.match(r'^(?:[•●▪◦]|[-–]\s)\s*',plain))
        if sum(plain.count(mark) for mark in ('•','●','▪','◦'))>1:return block,None
        shapes=[(i,s) for i,s in enumerate(geometry['shapes']) if s.get('fill') and
            1.3<=s['x1']-s['x0']<=6 and 1.3<=s['bottom']-s['top']<=6 and
            .7<=(s['x1']-s['x0'])/(s['bottom']-s['top'])<=1.4 and
            2<=line['x0']-s['x1']<=line['font_size']*1.8 and
            line['top']<=((s['top']+s['bottom'])/2)<=line['bottom'] and
            (s.get('non_stroking_color') in (0,0.0,[0],[0.0],[0,0,0],[0.0,0.0,0.0]))]
        vector.append(shapes[0][0] if len(shapes)==1 and not explicit else None)
        starts.append(explicit or len(shapes)==1)
    if sum(starts)<2:return block,None
    # Each line must be a single text column; large internal gaps expose
    # interleaved columns/cells and are left for the inherited risk queue.
    for line in lines:
        chars=sorted((c for c in line['chars'] if c['text'].strip()),key=lambda c:c['x0'])
        if any(z['x0']-a['x1']>max(a['size'],z['size'])*2.5 for a,z in zip(chars,chars[1:])):return block,None
    lefts=[l['x0'] for l,start in zip(lines,starts) if start]
    if max(lefts)-min(lefts)>3:return block,None
    pieces=[];encoded=[]
    for line,start,shape in zip(lines,starts,vector):
        value=rich_line(line)
        if start:
            if shape is not None:value='- '+value
            else:
                marker=re.match(r'^(\*\*)?([•●▪◦–-])\s*',value)
                if marker:
                    encoded.append(dict(source_line=line['index'],original_marker=marker[2]))
                    value='- '+(marker[1] or '')+value[marker.end():]
            pieces.append(value)
        elif pieces:pieces[-1]+=' '+value
        else:pieces.append(value)
    text='\n'.join(pieces)
    return {**block,'text':text},dict(block_id=block['id'],page=block['page'],method='Native one-column list starts and exact text reflow',
        source_lines=block['source_lines'],vector_shape_indices=[v for v in vector if v is not None],
        encoded_marker_replacements=encoded,
        added_bullet_characters=2*sum(v is not None for v in vector),technical_text_changed=False)


def assemble(accepted,r2,r3a,r3b,out):
    if out.exists():raise ValueError('Choose a new versioned R3C workspace')
    protected=[accepted.resolve(),r2.resolve(),r3a.resolve(),r3b.resolve(),r2.parent/'stage-2b2-real-world-20261111-r1',Path(r'C:\ROOT')]
    if any(out.resolve().is_relative_to(p) or p.is_relative_to(out.resolve()) for p in protected):raise ValueError('Separate external staging required')
    if any((p/'.obsidian').exists() for p in (out,*out.parents)):raise ValueError('Vault output forbidden')
    before=verify_inputs(accepted,r2,r3a,r3b);out.mkdir(parents=True);write(out/'integrity-before.json',before)
    baseline=load(accepted/'source-manifest.json');units=copy.deepcopy(baseline['source_units'])
    if len(units)!=24 or next(u['commit'] for u in units if u['id']=='postgresql-17-runtime-config-wal')!=WAL_COMMIT:raise ValueError('Source selection/WAL pin mismatch')
    # Public original snapshots/assets/licenses are copied byte-for-byte.
    copied=[]
    for directory in ('originals','assets','licenses','provenance','upstream'):
        for source in sorted((accepted/directory).rglob('*')):
            if source.is_file():
                target=out/source.relative_to(accepted);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
                if digest(source)!=digest(target):raise ValueError('Public input copy mismatch')
                copied.append(dict(path=target.relative_to(out).as_posix(),sha256=digest(target)))
    (out/'normalized').mkdir(exist_ok=True);(out/'maps').mkdir(exist_ok=True)
    for source in sorted((accepted/'maps').glob('*')):
        if source.is_file() and not source.name.startswith('prusa-'):shutil.copyfile(source,out/'maps'/source.name)
    patches=load(r3b/'experimental-corrections.json');by_page={(p['source_id'],p['page']):p for p in patches['pages']}
    if len(patches['changes'])!=22 or len(by_page)!=20:raise ValueError('Expected exactly 22 demonstrated repairs on 20 pages')
    availability=load(r3b/'availability-register.json');regions={(p['source_id'],p['page']):p for p in availability}
    all_availability=[];representations=[];applied=[];images=[]
    for u in units:
        sid=u['id'];target=out/u['normalized_path']
        if u['family']!='prusa':
            shutil.copyfile(accepted/u['normalized_path'],target)
            if digest(target)!=u['normalized_sha256']:raise ValueError('Unchanged text unit differs')
            u['candidate_status']='unchanged-copy-not-admitted';u['source_map']=f'maps/{sid}.json'
            continue
        old=(accepted/u['normalized_path']).read_text(encoding='utf-8');prefix=old[:u['body_offset']]
        prefix=re.sub(r'(?m)^status:.*$', 'status: source-once-candidate-not-admitted',prefix)
        pieces=[prefix];offset=len(prefix);records=[];pages=[];blocks_all=[];list_changes=[]
        original_sha=digest(out/u['original_path']);pdf_ref=f'../originals/{sid}.pdf'
        for number in range(1,u['page_count']+1):
            geometry=load(r2/'geometry'/sid/f'{number:03d}.json');structured=r2/'structured'/sid/f'{number:03d}.json'
            source_blocks=copy.deepcopy(load(structured)['blocks']);layer='r2-source-objects'
            if (sid,number) in by_page:
                item=by_page[sid,number];patch_path=r3b/'corrected-maps'/f'{sid}-p{number:03d}.json';patch=load(patch_path)
                patch_identity(u,original_sha,digest(structured),patch)
                if digest(r3b/item['path'])!=item['sha256'] or natural(patch['source_blocks'])[0]!=(r3b/item['path']).read_text(encoding='utf-8'):raise ValueError('R3B repair artifact mismatch')
                source_blocks=copy.deepcopy(patch['source_blocks']);layer='verified-r3b-overlay'
                applied.extend({**change,'source_pdf_sha256':original_sha,'expected_structured_sha256':digest(structured),'repair_map_sha256':digest(patch_path),'applied':True}
                               for change in patches['changes'] if (change['source_id'],change['page'])==(sid,number))
            # Preserve all original page pixels, including small icons, within
            # unchanged PDF and a hashed original full-page raster reference.
            render=r2/'page-renders'/sid/f'page-{number:03d}.png';render_target=out/'assets/prusa-pages'/sid/render.name
            render_target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(render,render_target)
            render_rel=render_target.relative_to(out).as_posix();render_sha=digest(render_target)
            page_start=offset;region=regions.get((sid,number));inserted=False
            for original_block in source_blocks:
                if region and not inserted and original_block['id'] in region['source_block_ids']:
                    ar=next(r for r in region['mapping'] if r['id'].endswith(':r3b-availability'))
                    marked=(r3b/region['excerpt_path']).read_text(encoding='utf-8')[ar['start']:ar['end']]
                    a=offset;pieces.append(marked);offset+=len(marked)
                    records.append(dict(id=ar['id'],page=number,kind='derived-availability',start=a,end=offset,source_lines=[],publisher_text=False))
                    all_availability.append({k:v for k,v in region.items() if k!='mapping'}|dict(start=a,end=offset,derived=True,source_id=sid,
                        source_pdf_sha256=original_sha,original_r3b_register_sha256=digest(r3b/'availability-register.json')))
                    inserted=True
                b,change=list_presentation(original_block,geometry)
                if change:list_changes.append(change)
                text,mapping=natural([b]);record=mapping[0]
                if b['kind']=='figure':
                    text+=f'![Original PDF page {number}](../{render_rel})\n\n[Original PDF page {number}]({pdf_ref}#page={number})\n\n'
                a=offset;pieces.append(text);offset+=len(text)
                shifted={**record,'start':a,'end':offset,'source_text_start':a+record['source_text_start'],'source_text_end':a+record['source_text_end'],
                         'cells':[{**cell,'start':a+cell['start'],'end':a+cell['end']} for cell in record['cells']],
                         'publisher_text':b['kind']!='figure','source_layer':layer,'source_bbox':b.get('bbox',b.get('source_bbox')),
                         'render_path':render_rel if b['kind']=='figure' else None,'source_pdf_page':number}
                records.append(shifted);blocks_all.append(b)
            if region and not inserted:raise ValueError('Availability source region did not resolve')
            for index,im in enumerate(geometry['images'],1):
                images.append(dict(source_id=sid,page=number,object_index=index,object=im,render_path=render_rel,
                    source_pdf_path=u['original_path'],source_pdf_sha256=original_sha,visual_meaning='unavailable-or-unreviewed; no inferred description'))
            pages.append(dict(page=number,start=page_start,end=offset,blank_native_text=not source_blocks,
                source_block_ids=[b['id'] for b in source_blocks],source_layer=layer,structured_input_sha256=digest(structured),
                geometry_input_sha256=digest(r2/'geometry'/sid/f'{number:03d}.json'),render_path=render_rel,render_sha256=render_sha))
        full=''.join(pieces);target.write_text(full,encoding='utf-8',newline='\n')
        block_index={b['id']:b for b in blocks_all}
        for record in records:
            if record['kind']=='derived-availability':
                record['text_origin']='derived-availability';record['contains_publisher_text']=False
                record['derived_segments']=[dict(start=record['start'],end=record['end'],kind='derived-region-availability')]
                record.pop('publisher_text',None)
            else:record_origins(record,block_index[record['id']],full)
        if len({b['id'] for b in blocks_all})!=len(blocks_all):raise ValueError('Duplicate primary source block ID')
        write(out/'maps'/f'{sid}.json',dict(source_pdf_sha256=original_sha,body_offset=len(prefix),records=records,pages=pages,
            source_blocks=blocks_all,representation_changes=list_changes,scope='Primary source once; original authored repetitions retained; page footers remain in original PDF/geometry'))
        u.update(normalized_sha256=digest(target),normalized_bytes=target.stat().st_size,normalized_characters=len(full),body_characters=len(full)-len(prefix),body_offset=len(prefix),
                 verification_status='source-once-candidate-not-admitted',candidate_status='not-admitted-not-frozen',source_map=f'maps/{sid}.json',
                 extraction=dict(method='R3A source-once representation over pinned R2 native objects, hash-gated R3B repairs',
                    tools={'representation_python':'3.14.7','input_pdfplumber':'0.11.9','input_pdf_python':'3.12.14','original_page_renders':'Poppler 26.07.0'},
                    transformations=['No H6 packets or chunk-size-dependent warning duplication','Natural source headings, paragraphs, explicit lists and native tables',
                                     '22 reviewed repair operations on 20 pages; no publisher wording/translation fixes','Exact R3B availability markers retained as derived metadata',
                                     'Original PDF/page pixels and image-object provenance retained; no OCR/image descriptions']))
        u.pop('language_map',None);u.pop('language_characters',None)
        u['language_review_status']='Original source language unchanged, including authentic untranslated passages; no new passage-level certification'
        representations.append(dict(source_id=sid,pages=len(pages),blocks=len(blocks_all),list_blocks_reflowed=len(list_changes),normalized_path=u['normalized_path'],normalized_sha256=digest(target)))
        print('Assembled',sid,len(full)-len(prefix),'body characters',flush=True)
    write(out/'source-manifest.json',dict(task='3C.2A-R3C',date='2026-11-11',status='candidate-only-no-admission-no-freeze',source_units=units,
        source_selection_preserved=24,pinned_postgresql_WAL_commit=WAL_COMMIT,input_workspaces={'accepted':str(accepted),'r2':str(r2),'r3a':str(r3a),'r3b':str(r3b)},
        notice='Neither source availability maps nor sidecars are automatically delivered to the LLM. All inherited limitations remain open.'))
    write(out/'applied-repairs.json',dict(repair_operations=applied,pages=sorted([dict(source_id=sid,page=p) for sid,p in by_page],key=lambda x:(x['source_id'],x['page'])),
        input_r3b_inventory_sha256=R3B_SHA));write(out/'availability-register.json',all_availability)
    write(out/'image-object-register.json',images);write(out/'assembly-results.json',representations);write(out/'unchanged-copy-hashes.json',copied)
    for name in ('outstanding-risk-register.json','uninspected-high.csv','inspection-decisions.json','triage-results.json','admission-policy-proposal.json'):
        target=out/'inherited-r3b'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(r3b/name,target)
    write(out/'mandatory-human-review-gates.json',load(r3b/'triage-results.json')['mandatory_human_review_pages'])
    relationships=[]
    for group in load(r3b/'procedure-decisions.json'):
        mapping=load(out/'maps'/f'{group["source_id"]}.json');by_id={b['id']:b for b in mapping['records']}
        ids=group['source_blocks_once'];missing=[i for i in ids if i not in by_id]
        if missing:raise ValueError('Reviewed scope source IDs missing: '+str(missing))
        relationships.append({**group,'source_ranges':[{k:by_id[i][k] for k in ('id','page','start','end')} for i in ids],
            'offset_basis':'R3C normalized file, LF-normalized Unicode characters','sidecar_delivery_to_llm':False})
    write(out/'warning-applicability-reviewed.json',relationships)
    write(out/'warning-applicability-unreviewed.json',dict(status='historical proposals, not verified applicability or mandatory prerequisites',
        input_r2_sha256=digest(r2/'dependency-relations.json'),relations=load(r2/'dependency-relations.json'),sidecar_delivery_to_llm=False))
    after=verify_inputs(accepted,r2,r3a,r3b)
    if before!=after:raise ValueError('Prior workspace integrity changed')
    write(out/'integrity-after-assembly.json',after)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('accepted','r2','r3a','r3b','output'):ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();assemble(args.accepted,args.r2,args.r3a,args.r3b,args.output)
