"""Offline content/source audit and dry chunk sizing; never constructs a store."""
from __future__ import annotations
import argparse
from collections import Counter
from html import unescape
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from normalize_real_world import DOM
from laew.rag.knowledge_base import KnowledgeBase


def words(text):
    return ' '.join(re.findall(r'\w+',unescape(text).casefold()))


def visible(text):
    text=re.sub(r'\[([^\]]*)\]\([^\n]*?\)',r'\1',text)
    text=re.sub(r'<a\b[^>]*>.*?</a>','',text)
    return words(text)


def section_html(raw,selector):
    return next(n for n in DOM(raw).root.walk() if n.attrs.get('id')==selector)


def audit(root):
    manifest=json.loads((root/'source-manifest.json').read_text(encoding='utf-8'))
    docs=[];pg=[];git=[]
    for u in manifest['source_units']:
        if 'normalized_path' not in u:continue
        text=(root/u['normalized_path']).read_text(encoding='utf-8');body=text[u['body_offset']:]
        record={'id':u['id'],'language':u['language'],'characters':len(text),'body_characters':len(body),'bytes':len(text.encode()),'chunks':{}}
        for strategy in ('legacy','structure-v2'):
            # Bypass __init__: no store, router, provider, embedding service or configuration lookup.
            kb=object.__new__(KnowledgeBase);kb.chunk_size=1000;kb.chunk_overlap=200;kb.chunking_strategy=strategy
            chunks=kb._load_file(root/u['normalized_path'],'global',root/'normalized',content=text,embed=False)
            assert chunks and all(c.embedding is None for c in chunks)
            assert all(c.metadata.get('frontmatter',{}).get('title') for c in chunks)
            record['chunks'][strategy]=len(chunks)
            if strategy=='structure-v2':
                intervals=sorted((c.metadata['start_offset'],c.metadata['end_offset']) for c in chunks)
                record['structure_source_span_bounds']=[intervals[0][0],intervals[-1][1]]
        record['headings']=len(re.findall(r'^#{1,6} ',body,re.M))
        record['unicode_replacement_characters']=body.count('\ufffd')
        docs.append(record)
        if u['family']=='progit':
            original=(root/u['original_path']).read_text(encoding='utf-8')
            src_code=re.findall(r'^----\n(.*?)^----$',original,re.M|re.S)
            dst_code=re.findall(r'^```[^\n]*\n(.*?)^```$',body,re.M|re.S)
            assert src_code==dst_code,(u['id'],'code block changed')
            src_headings=re.findall(r'^={3,} (.+)$',re.sub(r'^----\n.*?^----$','',original,flags=re.M|re.S),re.M)
            dst_headings=re.findall(r'^#{1,6} (.+)$',re.sub(r'^```[^\n]*\n.*?^```$','',body,flags=re.M|re.S),re.M)
            assert src_headings==dst_headings,(u['id'],'heading changed')
            assert not re.search(r'include::',original),'Unresolved source include'
            tree=json.loads((root/f'provenance/{u["repository"].split("/")[-1]}-tree.json').read_text(encoding='utf-8'))
            blob=next(x['sha'] for x in tree['tree'] if x['path']==u['source_path'])
            import hashlib
            raw=(root/u['original_path']).read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            assert blob==actual,(u['id'],'Git object identity mismatch')
            git.append(dict(id=u['id'],git_blob_sha1=blob,blob_verified=True,headings=len(src_headings),code_blocks=len(src_code),assets=len(u.get('assets',[])),
                all_assets_present=all((root/a['path']).is_file() for a in u.get('assets',[]))))
        elif u['family']=='postgresql':
            source=(root/u['upstream_path']).read_text(encoding='utf-8')
            topic=u['id'].split('-',2)[2]
            if topic=='backup':source=source.split('<sect1',1)[0]
            else:
                m=re.search(r'<sect1\b[^>]*\bid="'+re.escape(topic)+'"[^>]*>(.*?)</sect1>',source,re.S)
                assert m,(u['id'],'source section missing');source=m[1]
            source=re.sub(r'<!--.*?-->','',source,flags=re.S)
            source=re.sub(r'<indexterm\b.*?</indexterm>','',source,flags=re.S)
            paragraphs=re.findall(r'<para\b[^>]*>(.*?)</para>',source,re.S)
            raw=(root/u['original_path']).read_text(encoding='utf-8')
            section=section_html(raw,'BACKUP' if topic=='backup' else topic.upper())
            rendered=words(section.text())
            matched=[];unmatched=[];references=[];generated_matched=[]
            for p in paragraphs:
                plain=unescape(re.sub(r'<[^>]+>','',p));canonical=words(plain)
                if re.search(r'<xref\b|&[A-Za-z][A-Za-z0-9_.-]*;',p):
                    references.append(plain.strip())
                    marked=p
                    marked=re.sub(r'<xref\b[^>]*>',' REFPLACEHOLDER ',marked)
                    marked=re.sub(r'<[^>]+>','',marked)
                    marked=unescape(marked)
                    marked=re.sub(r'&[A-Za-z][A-Za-z0-9_.-]*;',' REFPLACEHOLDER ',marked)
                    spans=[words(s) for s in marked.split('REFPLACEHOLDER') if words(s)]
                    rest=rendered;ok=True
                    for span in spans:
                        pos=rest.find(span)
                        if pos<0:ok=False;break
                        rest=rest[pos+len(span):]
                    if ok:generated_matched.append(plain.strip())
                    else:unmatched.append(plain.strip())
                    continue
                (matched if canonical in rendered else unmatched).append(plain.strip())
            mapping=json.loads((root/f'maps/{u["id"]}.json').read_text(encoding='utf-8'))['records']
            normalized=visible(body)
            missing_headings=[h for h in mapping['headings'] if words(h) not in normalized]
            pre_coverage=[]
            for block in mapping['pre_blocks']:
                lines=[line.rstrip() for line in block.strip('\n').splitlines()]
                pre_coverage.append(all(line.strip() in body for line in lines if line.strip()))
            pg.append(dict(id=u['id'],release_tag=u['release_tag'],commit=u['commit'],source_paragraphs=len(paragraphs),
                exact_paragraph_matches=len(matched),unmatched_paragraphs=unmatched,paragraphs_with_generated_references_or_entities=len(references),
                generated_reference_paragraphs_matched=len(generated_matched),
                headings=len(mapping['headings']),missing_headings=missing_headings,preformatted_blocks=len(pre_coverage),
                all_preformatted_lines_preserved=all(pre_coverage),tables=mapping['table_count']))
    alltext=[(u['id'],(root/u['normalized_path']).read_text(encoding='utf-8')[u['body_offset']:]) for u in manifest['source_units'] if 'normalized_path' in u]
    duplicates=[]
    for i,(aid,a) in enumerate(alltext):
        for bid,b in alltext[i+1:]:
            if a==b:duplicates.append([aid,bid])
    summary=dict(documents=docs,unit_count=len(docs),body_characters=sum(d['body_characters'] for d in docs),
        normalized_characters=sum(d['characters'] for d in docs),normalized_bytes=sum(d['bytes'] for d in docs),
        original_bytes=sum((root/u['original_path']).stat().st_size for u in manifest['source_units']),
        nominal_language_units=dict(Counter(u['language'] for u in manifest['source_units'])),
        primary_language_units_excluding_substantial_fallback=dict(Counter(u['language'] for u in manifest['source_units'] if u.get('language_status','pending').startswith('authentic'))),
        long_documents=[d['id'] for d in docs if d['body_characters']>30000],
        chunks={s:sum(d['chunks'][s] for d in docs) for s in ('legacy','structure-v2')},
        exact_duplicate_bodies=duplicates,progit=git,postgresql=pg,
        note='Dry parser counts, no embeddings/stores/indexes/retrieval. Passage-level language counts are agent-screened, not human-certified.')
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    result=audit(args.root);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('documents','progit','postgresql')},indent=2))
    for p in result['postgresql']:print(p['id'],'source prose matches',p['exact_paragraph_matches'],'unmatched',len(p['unmatched_paragraphs']),'reference paragraphs',p['paragraphs_with_generated_references_or_entities'])
