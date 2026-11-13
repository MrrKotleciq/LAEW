"""Deterministic, offline normalization of the public Task 3C.2A corpus."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import dataclass,field
import hashlib
from html import escape
from html.parser import HTMLParser
import importlib.metadata
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
import html2text

from acquire_real_world import safe_root, sha


@dataclass
class Node:
    tag: str
    attrs: dict=field(default_factory=dict)
    children: list=field(default_factory=list)
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child,Node): yield from child.walk()
    def text(self):
        return ''.join(c.text() if isinstance(c,Node) else c for c in self.children)
    def html(self):
        attrs=''.join(f' {k}="{escape(v or "",quote=True)}"' for k,v in self.attrs.items())
        inner=''.join(c.html() if isinstance(c,Node) else escape(c) for c in self.children)
        return f'<{self.tag}{attrs}>{inner}</{self.tag}>'


class DOM(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=True); self.root=Node('document'); self.stack=[self.root]; self.feed(text)
    def handle_starttag(self,tag,attrs):
        node=Node(tag,dict(attrs)); self.stack[-1].children.append(node)
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}: self.stack.append(node)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if self.stack[-1].tag==tag:self.stack.pop()
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:
                del self.stack[i:]; break
    def handle_data(self,data): self.stack[-1].children.append(data)


def ascii_markdown(text,unit):
    """Convert the syntax used by these 12 source files; retain prose/code verbatim."""
    result=[]; mapping=[]; fence=False; language=''; callout=False
    local_anchors=set(re.findall(r'^\[\[(.+?)\]\]$',text,re.M))
    refs=unit.get('reference_links',[])
    def crossref(match):
        target=match[1];label=match[2] if match.lastindex==2 else None
        if target in local_anchors:return f'[{label or target}](#{target})'
        key=target.split('#')[-1]
        found=next((r for r in refs if r['href'].endswith('/'+key) or r['href'].endswith('#'+key)),None)
        if found:return f'[{label or found["text"]}]({found["href"]})'
        # Preserve unresolved upstream references visibly instead of fabricating a destination/title.
        return '\\<<'+target+(','+label if label else '')+'>>'
    for i,line in enumerate(text.splitlines(),1):
        start=sum(len(x)+1 for x in result)
        m=re.fullmatch(r'\[source,([^\]]+)\]',line)
        if m: language=m[1]; output=[]
        elif line=='----':
            result.append('```' if fence else '```'+language); fence=not fence; output=None
        elif fence: result.append(line); output=None
        elif re.fullmatch(r'\[\[(.+?)\]\]',line):
            result.append('<a id="'+re.fullmatch(r'\[\[(.+?)\]\]',line)[1]+'"></a>'); output=None
        elif re.match(r'^={3,} ',line):
            m=re.match(r'^(=+) (.*)',line); result.append('#'*(len(m[1])-2)+' '+m[2]); output=None
        elif line in ('[NOTE]','[TIP]','[WARNING]','[CAUTION]','[IMPORTANT]'):
            result.append('**'+line[1:-1]+'**');output=None
        elif line=='====': output=[]  # AsciiDoc example delimiters; contents retained.
        elif line=='[small]': output=[]
        elif line.startswith('//'): output=[]  # Non-published editorial comments only.
        else:
            line=re.sub(r'\(\(\(.*?\)\)\)','',line)
            line=line.replace('+++','')
            line=re.sub(r'<<([^,>]+),([^>]+)>>',crossref,line)
            line=re.sub(r'(?<!\\)<<([^,>]+)>>',crossref,line)
            m=re.fullmatch(r'image::([^\[]+)\[(.*)\]',line)
            if m:
                asset=next(a for a in unit['assets'] if a['source']==m[1])
                line=f'![{m[2]}](../{asset["path"]})'
            elif re.match(r'^\.[^ .]',line): line=line[1:]  # Figure/block caption.
            result.append(line);output=None
        mapping.append(dict(source_line=i,start=start,end=sum(len(x)+1 for x in result)))
    assert not fence,'Unclosed source listing'
    return '\n'.join(result)+'\n',mapping


def pg_markdown(raw,unit):
    dom=DOM(raw)
    wanted={'postgresql-17-backup':'BACKUP'}.get(unit['id'],unit['id'].split('-',2)[2].upper())
    selected=[n for n in dom.root.walk() if n.attrs.get('id')==wanted]
    assert len(selected)==1,(wanted,len(selected))
    section=selected[0]
    for n in section.walk():
        for key in ('href','src'):
            if key in n.attrs:n.attrs[key]=urljoin(unit['canonical_url'],n.attrs[key])
    def convert_html(value):
        convert=html2text.HTML2Text();convert.body_width=0;convert.unicode_snob=True
        convert.inline_links=True;convert.wrap_links=False;convert.ignore_images=False
        return convert.handle(value)
    # Keep every HTML anchor in a sidecar section map, including parameter IDs.
    anchors=[dict(id=n.attrs['id'],text=n.text().strip()[:240]) for n in section.walk() if 'id' in n.attrs]
    headings=[n.text() for n in section.walk() if re.fullmatch(r'h[1-6]',n.tag)]
    blocks=[n.text() for n in section.walk() if n.tag=='pre']
    stats=dict(headings=headings,anchors=anchors,pre_blocks=blocks,
               table_count=sum(n.tag=='table' for n in section.walk()),
               paragraph_count=sum(n.tag=='p' for n in section.walk()),
               source_visible_characters=len(section.text()),selector=f'div#{wanted}')
    tables={}
    def replace_tables(node):
        for index,child in enumerate(node.children):
            if not isinstance(child,Node):continue
            if child.tag=='table':
                rows=[];header=False
                for tr in (x for x in child.walk() if x.tag=='tr'):
                    cells=[x for x in tr.children if isinstance(x,Node) and x.tag in ('th','td')]
                    if not cells:continue
                    if not rows:header=any(c.tag=='th' for c in cells)
                    if any(c.attrs.get('rowspan','1')!='1' or c.attrs.get('colspan','1')!='1' for c in cells):
                        raise ValueError('Complex HTML table needs explicit normalization review')
                    rows.append([convert_html(''.join(x.html() if isinstance(x,Node) else escape(x) for x in c.children)).strip().replace('|',r'\|').replace('\n','<br>') for c in cells])
                width=max(map(len,rows));rows=[r+['']*(width-len(r)) for r in rows]
                if not header:rows.insert(0,['']*width)
                lines=['| '+' | '.join(r)+' |' for r in rows]
                lines.insert(1,'| '+' | '.join(['---']*width)+' |')
                marker=f'LAEWTABLEPLACEHOLDER{len(tables)}'
                tables[marker]='\n\n'+'\n'.join(lines)+'\n\n'
                node.children[index]=Node('p',{},[marker])
            else:replace_tables(child)
    replace_tables(section)
    md=convert_html(section.html())
    for marker,table in tables.items():md=md.replace(marker,table)
    assert 'LAEWTABLEPLACEHOLDER' not in md
    return md,stats


def passages(body,language,unit):
    records=[]; fenced=False; offset=0
    transitions={'progit-config-pl':'### `core.whitespace`',
                 'progit-submodules-pl':'## Working on a Project with Submodules'}
    start=body.find(transitions.get(unit['id'],'\x00'))
    for text in body.splitlines(keepends=True):
        fence=text.startswith('```')
        code=fenced or fence or text.startswith('    ') or text.startswith('<a ') or text.startswith('<!--')
        if fence:fenced=not fenced
        lang='en' if language=='pl' and start>=0 and offset>=start else language
        # Actual untranslated heading found on PDF page 2 of MK4; do not relabel German prose.
        if 'IMPORTANT INFORMATION REGARDING ORIGINAL PRUSA MK3.9:' in text:lang='en'
        label='code-or-markup' if code else lang if text.strip() else 'whitespace'
        if records and records[-1]['language']==label:records[-1]['end']+=len(text)
        else:records.append(dict(start=offset,end=offset+len(text),language=label,
                method='source language with agent-reviewed untranslated transitions; code is language-neutral'))
        offset+=len(text)
    return records


REVISIONS={
    'prusa-mk4s-en':('1.01','2024-09-26',['MK4S','MK3.9S']),
    'prusa-mmu3-en':('1.03','2025-05-15',['MMU3 with MK3S+ / MK3.5 / MK3.5S / MK3.9 / MK3.9S / MK4 / MK4S / CORE One']),
    'prusa-mk4-de':('1.03','2023-09-04',['MK4','MK3.9']),
    'prusa-xl-de':('1.06','2026-01-22',['XL single-tool','XL multi-tool']),
    'prusa-mini-pl':('1.09','2022-04-05',['MINI','MINI+']),
    'prusa-mk3s-pl':('3.17','2021-04-21',['MK3S','MK3S+'])}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',required=True);args=ap.parse_args()
    root=safe_root(args.root)
    for d in ('normalized','maps','verification'): (root/d).mkdir(exist_ok=True)
    units=json.loads((root/'acquired-units.json').read_text(encoding='utf-8'))
    for u in units:
        if u['family']=='prusa' and not (root/f'extraction/{u["id"]}.json').exists():
            u['verification_status']='acquired-awaiting-extraction'
            print('Waiting for PDF extraction:',u['id']);continue
        original=root/u['original_path'];raw=original.read_bytes();u['original_sha256']=sha(raw);u['original_bytes']=len(raw)
        u['retrieved_at']=json.loads(original.with_suffix(original.suffix+'.http.json').read_text(encoding='utf-8'))['retrieved_at']
        warnings=[];status='verified-with-limitations'
        if u['family']=='progit':
            rendered_raw=(root/u['rendered_path']).read_text(encoding='utf-8')
            rendered_section=next(n for n in DOM(rendered_raw).root.walk() if n.attrs.get('id')=='main')
            u['reference_links']=[dict(text=n.text().strip(),href=urljoin(u['canonical_url'],n.attrs['href'])) for n in rendered_section.walk() if n.tag=='a' and n.attrs.get('href') and n.text().strip()]
            body,mapping=ascii_markdown(raw.decode('utf-8'),u)
            u['revision']='Pro Git second edition; '+u['commit']
            u['applicable_versions']='Git 2.x as documented at this language commit; translations are not synchronized releases'
            u['license']={'id':'CC-BY-NC-SA-3.0','notice_path':f'licenses/progit-{u["language"]}-LICENSE.asc','redistribution':'Attribution, noncommercial use, ShareAlike; commercial use not authorized by this license'}
            u['extraction']={'method':'Complete pinned AsciiDoc -> conservative line-based Markdown conversion','source_line_map':f'maps/{u["id"]}.json',
                'transformations':['Headings = -> # with level offset -2','Listing delimiters -> fenced code; contents unchanged','Anchors and cross-references -> HTML anchors/Markdown links','Figure macros -> local image links','Example delimiters and style attributes removed; all published prose retained','No translation or summarization']}
            if u['language']=='pl' and u['id'] in ('progit-config-pl','progit-submodules-pl'):
                warnings.append('Substantial authentic English fallback; retained in full with user approval on 2026-11-11. Not a fully Polish unit.')
                u['language_status']='mixed-pl-en-user-approved'
            else:u['language_status']='authentic-'+u['language']
            rendered=root/u['rendered_path'];u['rendered_sha256']=sha(rendered.read_bytes())
            warnings.append('Rendered publisher snapshot retained separately; source normalization uses pinned repository content. Live render-to-commit equality must not be assumed.')
        elif u['family']=='postgresql':
            body,mapping=pg_markdown(raw.decode('utf-8'),u)
            v=u['major_version'];tag={'17':'REL_17_10','11':'REL_11_22','12':'REL_12_22'}[v]
            commit=json.loads((root/f'provenance/postgresql-{v}-commit.json').read_text(encoding='utf-8'))['sha']
            source='doc/src/sgml/'+('config.sgml' if 'runtime-config-wal' in u['id'] else 'appendix-obsolete-recovery-config.sgml' if 'recovery-config' in u['id'] else 'release-12.sgml' if 'release-12' in u['id'] else 'backup.sgml')
            u.update(commit=commit,release_tag=tag,source_path=source,repository='postgres/postgres',revision=tag+'; rendered official major-version page snapshot',
                applicable_versions='PostgreSQL '+v+(' (12.0 release notes retained in final 12.x documentation)' if v=='12' else ''))
            u['upstream_path']=f'upstream/postgresql-{v}/{source}'
            if u['id']=='postgresql-17-runtime-config-wal':
                stable=json.loads((root/'provenance/postgresql-17-stable-commit.json').read_text(encoding='utf-8'))['sha']
                u.update(commit=stable,release_tag=None,released_baseline_tag=tag,
                    revision='PostgreSQL 17 documentation; REL_17_STABLE commit '+stable,
                    upstream_path=f'upstream/postgresql-17-stable/{source}')
                warnings.append('Official moving /docs/17 WAL page includes a post-17.10 documentation correction (on is a historical spelling of pglz). Do not identify this snapshot as REL_17_10; exact current source commit is pinned separately.')
            u['license']={'id':'PostgreSQL','notice_path':f'upstream/postgresql-{v}/COPYRIGHT','redistribution':'Permitted with copyright and permission notice'}
            u['language_status']='authentic-en'
            u['extraction']={'method':'Official rendered HTML exact publisher section DOM -> html2text Markdown','transformations':['Select complete publisher section including nested subsections','Remove site header/footer/navigation outside section','Resolve relative hyperlinks to canonical publisher URLs','Preserve tables and preformatted listings'],'section_map':f'maps/{u["id"]}.json'}
            if 'backup'==u['id'].split('-',2)[2]:warnings.append('Complete backup.html overview page only; linked SQL dump/file-system chapters are not included, as proposed.')
            warnings.append('Released SGML source retained and pinned; rendered/source correspondence checked separately in verification/content-audit.json.')
        else:
            data=json.loads((root/f'extraction/{u["id"]}.json').read_text(encoding='utf-8'))
            pieces=[];mapping=[];offset=0
            for p in data['page_records']:
                text=p['text']
                # Preserve every extracted character; headings are annotations derived from source numbering.
                header=f'\n\n<!-- original PDF page {p["page"]} -->\n\n'
                result=[]
                for line in text.splitlines(keepends=True):
                    match=re.match(r'^(\d+(?:\.\d+)*\.?)\s+[^\n]+',line)
                    if match and '...' not in line and len(line.strip())<115 and not re.search(r'\s\d+\s*$',line):
                        depth=min(6,match[1].rstrip('.').count('.')+2)
                        # Require a heading-sized font, preventing numbered procedural steps becoming headings.
                        candidates=[r for r in p['lines'] if r['text'].strip()==line.strip()]
                        if candidates and max(r['max_font_size'] for r in candidates)>12:line='#'*depth+' '+line
                    result.append(line)
                chunk=header+''.join(result)
                pieces.append(chunk);mapping.append(dict(page=p['page'],start=offset,end=offset+len(chunk),text_characters=len(text),
                    image_count=len(p['images']),independent_token_agreement=p['token_agreement']))
                offset+=len(chunk)
            body=''.join(pieces).lstrip('\n'); shift=len(''.join(pieces))-len(body)
            for m in mapping:m['start']=max(0,m['start']-shift);m['end']-=shift
            rev,date,hardware=REVISIONS[u['id']]
            u.update(revision=rev,printed_revision_date=date,hardware=hardware,applicable_versions='Hardware '+', '.join(hardware)+'; firmware guidance belongs to the printed handbook date, not current firmware',page_count=data['pages'])
            u['license']={'id':'No-document-redistribution-grant-identified','notice_path':f'originals/{u["id"]}.pdf','redistribution':'Local research staging only. No redistribution authorization established. Hardware/firmware open-source licenses do not establish handbook licensing.'}
            u['language_status']='authentic-'+u['language']+(' with isolated English labels/headings' if u['language']!='en' else '')
            u['extraction']={'method':'pypdf per-page text; independently checked with pdfplumber','tools':data['tools'],
                'transformations':['All PDF pages included in order','Original page comments and source-numbered heading Markdown added','Original text retained without translation or paraphrase'],
                'page_map':f'maps/{u["id"]}.json','layout_and_independent_extraction':f'extraction/{u["id"]}.json',
                'minimum_page_token_agreement':min(p['token_agreement'] for p in data['page_records'])}
            warnings+=['UNSUITABLE FOR FREEZE: PDF diagrams, warning-icon association and table cell relationships are not fully represented/verified in text-only Markdown. Originals and independent layout extraction retained; no OCR or fabricated descriptions added.',
                       'Heading recovery is partial. Page mapping is complete; multi-line and unnumbered PDF heading hierarchy needs remediation before admission.']
            status='acquired-normalized-unsuitable-for-freeze'
        title=next((line.lstrip('# ').strip() for line in body.splitlines() if line.startswith('#')) ,u['id'])
        if u['family']=='prusa':title=f'Original Prusa {" / ".join(u["hardware"])} handbook {u["revision"]} ({u["language"]})'
        front='---\ntitle: '+json.dumps(title,ensure_ascii=False)+'\ntype: public-technical-source\nsource_id: '+u['id']+'\nlanguage: '+u['language']+'\nrevision: '+json.dumps(u['revision'])+'\nstatus: '+status+'\ntags: []\nbacklinks: []\n---\n'
        normalized=(front+body).encode('utf-8')
        u.update(normalized_path=f'normalized/{u["id"]}.md',normalized_sha256=sha(normalized),normalized_bytes=len(normalized),
            normalized_characters=len(normalized.decode('utf-8')),body_characters=len(body),body_offset=len(front),verification_status=status,warnings=warnings)
        (root/u['normalized_path']).write_bytes(normalized)
        (root/f'maps/{u["id"]}.json').write_text(json.dumps({'coordinates':'Unicode character offsets in Markdown body, after YAML frontmatter removal','records':mapping},ensure_ascii=False,indent=2),encoding='utf-8')
        ps=passages(body,u['language'],u)
        (root/f'maps/{u["id"]}-language.json').write_text(json.dumps(ps,ensure_ascii=False,indent=2),encoding='utf-8')
        u['language_map']=f'maps/{u["id"]}-language.json'
        u['language_characters']=dict(Counter({lang:sum(p['end']-p['start'] for p in ps if p['language']==lang) for lang in set(p['language'] for p in ps)}))
        print(u['id'],len(body),status)
    manifest=dict(schema='laew-public-corpus-1',task='3C.2A',created_date='2026-11-11',source_units=units,
        language_policy='Mixed Polish Pro Git retained in full, explicitly approved by user on 2026-11-11; passage screening is agent review, not bilingual human certification.',
        tools={'python':sys.version.split()[0],'html2text':importlib.metadata.version('html2text')},
        readiness='NOT FROZEN: PDF extraction defects require remediation; see verification and report')
    (root/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
