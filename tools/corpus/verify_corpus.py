"""Verify a local frozen inventory offline, without LAEW, models, or network access."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def verify(root):
    root=root.resolve()
    inventory=json.loads((root/'integrity-inventory.json').read_text(encoding='utf-8'))
    errors=[]
    for item in inventory['files']:
        path=(root/item['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():errors.append('Missing/unsafe: '+item['path'])
        elif path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:errors.append('Changed: '+item['path'])
    expected={x['path'] for x in inventory['files']}|{'integrity-inventory.json'}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    errors+=['Unrecorded: '+p for p in sorted(actual-expected)]
    manifest=json.loads((root/'source-manifest.json').read_text(encoding='utf-8'))
    ids=[u['id'] for u in manifest['source_units']]
    if len(ids)!=24 or len(set(ids))!=24:errors.append('Expected 24 distinct proposed unit IDs')
    for u in manifest['source_units']:
        for name,hashkey in [('original_path','original_sha256'),('normalized_path','normalized_sha256')]:
            path=(root/u[name]).resolve()
            if not path.is_relative_to(root) or not path.is_file() or digest(path)!=u[hashkey]:errors.append('Manifest mismatch: '+u['id']+'/'+name)
    return {'verified':not errors,'files_checked':len(inventory['files']),'units':len(ids),'errors':errors,
            'manifest_sha256':digest(root/'source-manifest.json'),'inventory_sha256':digest(root/'integrity-inventory.json')}


def inventory(root):
    records=[]
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name!='integrity-inventory.json':records.append(dict(path=path.relative_to(root).as_posix(),bytes=path.stat().st_size,sha256=digest(path)))
    (root/'integrity-inventory.json').write_text(json.dumps({'algorithm':'SHA-256','files':records},indent=2),encoding='utf-8')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--write-inventory',action='store_true');args=ap.parse_args()
    if args.write_inventory:inventory(args.root)
    result=verify(args.root);print(json.dumps(result,indent=2));sys.exit(0 if result['verified'] else 1)
