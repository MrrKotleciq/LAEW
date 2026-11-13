"""List English-function-word screening candidates outside literal source listings."""
import json
from pathlib import Path
import re
import sys
root=Path(sys.argv[1])
for path in sorted((root/'originals').glob('progit-*.asc')):
    if path.stem.endswith('-en'):continue
    candidates=[];fence=False
    for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if line=='----':fence=not fence;continue
        if fence:continue
        words=re.findall(r'\b[a-z]+\b',re.sub(r'`[^`]+`','',line).lower())
        signals=sum(w in {'the','you','your','this','these','when','will','with','that','which','would','because','have','has','are','and','can'} for w in words)
        if signals>=4 and len(words)>12:candidates.append({'source_line':i,'text':line})
    print(path.name,'English prose candidates',len(candidates),'source lines',[c['source_line'] for c in candidates])
    if candidates:print(candidates[0]['text'][:350])
for path in sorted((root/'extraction').glob('*.json')):
    data=json.loads(path.read_text(encoding='utf-8'))
    version=re.findall(r'[^\n]*(?:[Vv]ersion|wersji|[Hh]andbuch)[^\n]*',data['page_records'][1]['text'])
    print(path.stem,'page 2 revision',version[:6],'low-agreement pages',[(p['page'],p['token_agreement']) for p in data['page_records'] if p['token_agreement']<.95])
