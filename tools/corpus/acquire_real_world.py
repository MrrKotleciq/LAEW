"""Acquire public Task 3C.2A sources; never imports LAEW runtime or models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone
import urllib.parse
from html.parser import HTMLParser
import requests


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a' and dict(attrs).get('href'):
            self.links.append(dict(attrs)['href'])


def safe_root(value):
    root = Path(value).resolve()
    if root == Path(root.anchor) or root.is_relative_to(Path(r"C:\ROOT")):
        raise ValueError("Persistent corpus must be outside C:\\ROOT")
    if any((p / '.obsidian').is_dir() for p in (root, *root.parents)):
        raise ValueError("Corpus must be outside Obsidian vaults")
    return root


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True)
    ap.add_argument('--discover', action='store_true')
    ap.add_argument('--supplement', action='store_true')
    ap.add_argument('--replay-plan', type=Path, help='Re-fetch exact frozen URLs and require recorded byte hashes; no HEAD discovery')
    ap.add_argument('--pin-pg17-stable', action='store_true')
    args = ap.parse_args()
    root = safe_root(args.root)
    root.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'LAEW-corpus-acquisition/3C.2A (public documentation research)'

    if args.replay_plan:
        for item in json.loads(args.replay_plan.read_text(encoding='utf-8')):
            path=(root/item['path']).resolve()
            if not path.is_relative_to(root):raise ValueError('Unsafe replay path')
            if path.exists():
                if sha(path.read_bytes())!=item['sha256']:raise ValueError(f'Existing hash mismatch: {path}')
                continue
            response=session.get(item['url'],timeout=90);response.raise_for_status()
            if sha(response.content)!=item['sha256']:raise ValueError(f'Upstream bytes changed: {item["url"]}')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(response.content)
        return

    def get(url, rel):
        path = root / rel
        logpath = path.with_suffix(path.suffix + '.http.json')
        if path.exists() and logpath.exists():
            data=path.read_bytes();record=json.loads(logpath.read_text(encoding='utf-8'))
            if sha(data)!=record['sha256'] or record['requested_url']!=url:
                raise ValueError(f'Cached source identity/hash mismatch: {path}')
            return data
        response = session.get(url, timeout=90)
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = response.content
        path.write_bytes(data)
        logpath.write_text(json.dumps({'requested_url': url, 'resolved_url': response.url,
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'sha256': sha(data),
            'status': response.status_code, 'headers': dict(response.headers)}, indent=2), encoding='utf-8')
        return data

    if args.pin_pg17_stable:
        commit=json.loads(get('https://api.github.com/repos/postgres/postgres/commits/REL_17_STABLE','provenance/postgresql-17-stable-commit.json'))
        print('PostgreSQL 17 stable',commit['sha'],commit['commit']['committer']['date'])
        get(f'https://raw.githubusercontent.com/postgres/postgres/{commit["sha"]}/doc/src/sgml/config.sgml','upstream/postgresql-17-stable/doc/src/sgml/config.sgml')
        get('https://api.github.com/repos/postgres/postgres/commits?sha=REL_17_STABLE&path=doc/src/sgml/config.sgml&per_page=15','provenance/postgresql-17-config-history.json')
        return

    if args.supplement:
        import html
        raw=(root/'originals/progit-remote-branches-de.html').read_text(encoding='utf-8')
        links=Links(); links.feed(raw)
        corrected=[html.unescape(x) for x in links.links if 'Konfig' in x or 'Erste' in x]
        print('DE canonical links',*corrected,sep='\n')
        for v,tag in [('17','REL_17_10'),('11','REL_11_22'),('12','REL_12_22')]:
            ref=json.loads(get(f'https://api.github.com/repos/postgres/postgres/git/ref/tags/{tag}',f'provenance/postgresql-{v}-tag.json'))
            obj=ref['object']
            if obj['type']=='tag':
                obj=json.loads(get(obj['url'],f'provenance/postgresql-{v}-annotated-tag.json'))['object']
            print('PG',v,tag,obj)
            get(f'https://api.github.com/repos/postgres/postgres/commits/{obj["sha"]}',f'provenance/postgresql-{v}-commit.json')
            files=['COPYRIGHT','configure.ac' if v=='17' else 'configure.in','doc/src/sgml/backup.sgml']
            if v=='17': files+=['doc/src/sgml/config.sgml','doc/src/sgml/appendix-obsolete-recovery-config.sgml']
            if v=='12': files+=['doc/src/sgml/release-12.sgml']
            for file in files:
                try: get(f'https://raw.githubusercontent.com/postgres/postgres/{obj["sha"]}/{file}',f'upstream/postgresql-{v}/{file}')
                except requests.HTTPError as error: print('source failed',file,str(error))
        for path in sorted((root/'licenses').glob('*.asc')):
            print(path.name,path.read_text(encoding='utf-8')[:1700])
        units=json.loads((root/'acquired-units.json').read_text(encoding='utf-8'))
        for unit in units:
            if unit['id'] in ('progit-first-time-setup-de','progit-config-de'):
                slug='Erste-Schritte-Git-Basis-Konfiguration' if 'setup' in unit['id'] else 'Git-einrichten-Git-Konfiguration'
                unit['canonical_url']=f'https://git-scm.com/book/de/v2/{slug}'
                get(unit['canonical_url'],unit['rendered_path'])
            if unit['family']=='progit':
                text=(root/unit['original_path']).read_text(encoding='utf-8')
                tree=json.loads(get(f'https://api.github.com/repos/{unit["repository"]}/git/trees/{unit["commit"]}?recursive=1',f'provenance/{unit["repository"].split("/")[-1]}-tree.json'))
                unit['assets']=[]
                for asset in re.findall(r'image::([^\[]+)\[',text):
                    matches=[x['path'] for x in tree['tree'] if x['path'].endswith(asset)]
                    assert len(matches)==1,(unit['id'],asset,matches)
                    rel=f'assets/{unit["language"]}/{Path(asset).name}'
                    get(f'https://raw.githubusercontent.com/{unit["repository"]}/{unit["commit"]}/{matches[0]}',rel)
                    unit['assets'].append(dict(source=asset,source_path=matches[0],path=rel))
        get('https://creativecommons.org/licenses/by-nc-sa/3.0/legalcode.en','licenses/CC-BY-NC-SA-3.0.html')
        (root/'acquired-units.json').write_text(json.dumps(units,ensure_ascii=False,indent=2),encoding='utf-8')
        return

    catalog = get('https://help.prusa3d.com/pl/article/podreczniki-druku_125045', 'provenance/prusa-catalog-pl.html').decode()
    if args.discover:
        links = Links()
        links.feed(catalog)
        print('\n'.join(x for x in links.links if '.pdf' in x))
        for lang, model in [('en','mk4s'),('en','mmu3'),('de','mk4'),('de','xl'),('pl','mini'),('pl','mk3s')]:
            raw=get(f'https://help.prusa3d.com/{lang}/product/{model}', f'provenance/prusa-{model}-{lang}-product.html').decode()
            links=Links(); links.feed(raw)
            print(model,lang, '\n'.join(x for x in links.links if '.pdf' in x))
            print('embedded PDFs:', '\n'.join(sorted(set(re.findall(r'https[^<>"\s\\]+\.pdf', raw)))))
        for repo in ['progit/progit2','progit2-pl/progit2-pl','progit/progit2-de']:
            meta=json.loads(get(f'https://api.github.com/repos/{repo}/commits/HEAD', f'provenance/{repo.split("/")[-1]}-commit.json'))
            commit=meta['sha']
            tree=json.loads(get(f'https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1',f'provenance/{repo.split("/")[-1]}-tree.json'))
            print(repo,commit)
            print('\n'.join(x['path'] for x in tree['tree'] if re.search('setup|config|remote|submod|LICENSE|COPYING',x['path'],re.I)))
        return

    units=[]
    for lang, model in [('en','mk4s'),('en','mmu3'),('de','mk4'),('de','xl'),('pl','mini'),('pl','mk3s')]:
        raw=get(f'https://help.prusa3d.com/{lang}/product/{model}', f'provenance/prusa-{model}-{lang}-product.html').decode()
        links=Links(); links.feed(raw)
        urls=list(dict.fromkeys(x for x in links.links if '.pdf' in x))
        assert len(urls)==1, urls
        rel=f'originals/prusa-{model}-{lang}.pdf'
        get(urls[0],rel)
        units.append(dict(id=f'prusa-{model}-{lang}',family='prusa',language=lang,publisher='Prusa Research',
            url=urls[0],canonical_url=f'https://help.prusa3d.com/{lang}/product/{model}',original_path=rel))
        print('acquired',rel,flush=True)

    topics=[('first-time-setup','01-introduction'),('config','08-customizing-git'),('remote-branches','03-git-branching'),('submodules','07-git-tools')]
    slugs={
        'en':['Getting-Started-First-Time-Git-Setup','Customizing-Git-Git-Configuration','Git-Branching-Remote-Branches','Git-Tools-Submodules'],
        'pl':['Pierwsze-kroki-Wstępna-konfiguracja-Git','Dostosowywanie-Gita-Konfiguracja-Gita','Gałęzie-Gita-Gałęzie-zdalne','Narzędzia-Gita-Moduły-zależne'],
        'de':['Erste-Schritte-Git-erstmalig-einrichten','Git-anpassen-Git-Konfiguration','Git-Branching-Remote-Branches','Git-Tools-Submodule']}
    for lang,repo in [('en','progit/progit2'),('pl','progit2-pl/progit2-pl'),('de','progit/progit2-de')]:
        commit=json.loads(get(f'https://api.github.com/repos/{repo}/commits/HEAD', f'provenance/{repo.split("/")[-1]}-commit.json'))['sha']
        get(f'https://raw.githubusercontent.com/{repo}/{commit}/LICENSE.asc',f'licenses/progit-{lang}-LICENSE.asc')
        for (topic,chapter),slug in zip(topics,slugs[lang]):
            sid=f'progit-{topic}-{lang}'
            source=f'book/{chapter}/sections/{topic}.asc'
            rel=f'originals/{sid}.asc'
            get(f'https://raw.githubusercontent.com/{repo}/{commit}/{source}',rel)
            url=f'https://git-scm.com/book/{lang}/v2/{slug}'
            try:
                get(url,f'originals/{sid}.html')
            except requests.HTTPError as error:
                print('rendered snapshot failed',url,str(error),flush=True)
            units.append(dict(id=sid,family='progit',language=lang,publisher='Scott Chacon and Ben Straub / Pro Git translators',
                canonical_url=url,url=f'https://github.com/{repo}/blob/{commit}/{source}',repository=repo,commit=commit,source_path=source,original_path=rel,
                rendered_path=f'originals/{sid}.html'))
            print('acquired',sid,flush=True)
    for version,topic in [('17','continuous-archiving'),('17','runtime-config-wal'),('17','backup'),('17','recovery-config'),('11','continuous-archiving'),('12','release-12')]:
        sid=f'postgresql-{version}-{topic}'
        url=f'https://www.postgresql.org/docs/{version}/{topic}.html'
        rel=f'originals/{sid}.html'
        get(url,rel)
        units.append(dict(id=sid,family='postgresql',language='en',publisher='PostgreSQL Global Development Group',url=url,canonical_url=url,original_path=rel,major_version=version))
        print('acquired',sid,flush=True)
    get('https://www.postgresql.org/about/licence/', 'licenses/postgresql-license.html')
    get('https://raw.githubusercontent.com/progit/progit2/a013e3230a1207cfa5ae94d28ba7d2021063c337/TRANSLATING.md','provenance/progit-TRANSLATING.md')
    (root/'acquired-units.json').write_text(json.dumps(units,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
