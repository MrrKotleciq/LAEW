"""Read selected native PDF cells and rotated text with the bundled PDF runtime."""
import argparse
import json
from pathlib import Path
import pdfplumber

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();records={}
for sid,pn in [('prusa-mk4-de',7),('prusa-mk4-de',8),('prusa-mk4s-en',6),('prusa-mmu3-en',7),('prusa-xl-de',9),('prusa-xl-de',81)]:
    with pdfplumber.open(args.corpus/'originals'/f'{sid}.pdf') as pdf:
        table=pdf.pages[pn-1].find_tables()[-1]
        records[f'{sid}:{pn}']=dict(bbox=list(table.bbox),rows=table.extract(),cells=[list(r.cells) for r in table.rows])
for sid in ['prusa-mini-pl','prusa-mk4-de','prusa-mk4s-en','prusa-mmu3-en','prusa-xl-de']:
    with pdfplumber.open(args.corpus/'originals'/f'{sid}.pdf') as pdf:
        chars=[c for c in pdf.pages[0].chars if not c['upright']]
        records[f'{sid}:1']=dict(rotated_native_text=''.join(c['text'] for c in chars),chars=chars)
args.output.write_text(json.dumps(dict(tools={'pdfplumber':pdfplumber.__version__},records=records),ensure_ascii=False,indent=2),encoding='utf-8')
