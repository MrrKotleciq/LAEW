"""Extract complete PDF pages with local bundled pypdf/pdfplumber; no OCR or AI."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import pypdf
import pdfplumber


def tokens(text):
    return Counter(re.findall(r'\w+',text.casefold()))


def extract(root):
    out=root/'extraction'; out.mkdir(exist_ok=True)
    for path in sorted((root/'originals').glob('*.pdf')):
        target=out/(path.stem+'.json')
        if target.exists():
            previous=json.loads(target.read_text(encoding='utf-8'))
            if previous.get('original_sha256') and previous['original_sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f'Extraction cache refers to changed original: {path}')
            continue
        reader=pypdf.PdfReader(path)
        pages=[]
        with pdfplumber.open(path) as second:
            assert len(second.pages)==len(reader.pages)
            for i,(page,independent) in enumerate(zip(reader.pages,second.pages),1):
                plain=page.extract_text() or ''
                layout=page.extract_text(extraction_mode='layout',layout_mode_space_vertically=False) or ''
                other=independent.extract_text() or ''
                a,b=tokens(plain),tokens(other)
                agreement=sum((a&b).values())/max(1,sum(b.values()))
                images=[{'bbox':[im.get(k) for k in ('x0','top','x1','bottom')],
                         'width':im.get('width'),'height':im.get('height')} for im in independent.images]
                # Font records allow heading and warning-marker inspection without changing source text.
                runs=[]
                for line in independent.extract_text_lines(return_chars=True):
                    chars=line.pop('chars',[])
                    line['max_font_size']=max((c['size'] for c in chars),default=0)
                    line['fonts']=sorted(set(c['fontname'] for c in chars))
                    runs.append(line)
                pages.append(dict(page=i,text=plain,layout=layout,independent_text=other,
                    token_agreement=round(agreement,6),images=images,lines=runs))
        data=dict(source=path.name,original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages=len(pages),metadata={str(k):str(v) for k,v in (reader.metadata or {}).items()},
            tools={'python':sys.version.split()[0],'pypdf':pypdf.__version__,'pdfplumber':pdfplumber.__version__},page_records=pages)
        target.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        print(path.stem,len(pages),'pages; minimum independent token agreement',min(x['token_agreement'] for x in pages),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--root',type=Path,required=True)
    extract(ap.parse_args().root)
