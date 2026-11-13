"""Package local R2 candidate QA artifacts; never admit or freeze source documents."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from html import escape
import json
from pathlib import Path
import re
import shutil

from prusa_pdf_r2 import guard_inputs, sha, dump


# Component decisions from visual comparisons, not whole-page certifications.
REVIEW_CASES = [
    ('prusa-mk3s-pl',[12,13],'Corrected and verified','Numbered subsections','Small bold subsection headings recovered from source fonts; parent/child scope corrected.'),
    ('prusa-mk3s-pl',[12],'Not safely representable as text','Calibration flowchart','Arrow connections remain raster-dependent; source prose does not encode the complete decision graph.'),
    ('prusa-mk3s-pl',[15],'Corrected and verified','Icon paragraphs','Complete calibration/handling paragraphs reassembled; warranty retained as primary text, not a procedural prerequisite.'),
    ('prusa-mk3s-pl',[16],'Requires manual review','Two-column pros/cons','Words retained, but column polarity and tick/warning associations need manual mapping.'),
    ('prusa-mk3s-pl',[16],'Not safely representable as text','First-layer photographs','Visual acceptance criteria cannot be reconstructed from existing text alone.'),
    ('prusa-mk3s-pl',[35,36],'Corrected and verified','LCD menu and shared note','44 plus 49 items; page 36 resumes Ustawienia/HW ancestry; conditional branches and literal shared note survive actual chunks.'),
    ('prusa-xl-de',[7],'Verified correct','Blank page','Original has no source text or diagram; candidate invents no content.'),
    ('prusa-xl-de',[16,17,18],'Verified correct','Distinct published installation topics','Single-tool, multi-tool and manual unlocking text remain separate; photo-local note is not broadcast across the chapter.'),
    ('prusa-xl-de',[16,17,18],'Not safely representable as text','Installation illustrations','Arrow targets, part positions and photo-only relationships remain unresolved.'),
    ('prusa-xl-de',[23,24],'Corrected and verified','Sheet installation dependencies','Three original warning boxes plus original bold cleanliness/bed restriction repeated; finger-clearance warning stays with its own alignment paragraph.'),
    ('prusa-xl-de',[23],'Not safely representable as text','Alignment marks','Orange spatial alignment targets require the source image; embedding the page is not a text repair.'),
    ('prusa-xl-de',[62],'Requires manual review','Material pros/cons','Temperatures and wording retained; borderless two-column polarity and local applicability need manual adjudication.'),
    ('prusa-xl-de',[70],'Verified correct','Sheet usage/risk table cells','Smooth/textured/satin row and usage/risk column identity repeated in each cell fragment; IPA and acetone restrictions retained.'),
    ('prusa-xl-de',[81],'Requires manual review','PDU dimensions and merged cells','Text and numeric tokens retained; merged-cell relationships and safety-symbol interpretation are not certified.'),
    ('prusa-xl-de',[81],'Not safely representable as text','PDU safety symbols','No invented symbol descriptions; graphical meanings require reviewed mapping.'),
    ('prusa-mk4s-en',[18,19],'Corrected and verified','Selftest/calibration prerequisites','Bed-installed warning crosses the page; local no-touch/stability warning and literal 5 cm prerequisite accompany reviewed procedure fragments.'),
    ('prusa-mk4s-en',[58],'Verified correct','Sheet usage/risk table cells','Original row/column context and all source cell values retained in fragmented cells.'),
    ('prusa-mk4-de',[21,22],'Corrected and verified','Selftest/calibration prerequisites','Separate 4.3/4.4 scopes; bed-installed and local no-touch/stability warnings plus literal 5 cm prerequisite retained.'),
    ('prusa-mk4-de',[60],'Verified correct','Sheet usage/risk table cells','Original row/column context and all source cell values retained in fragmented cells.'),
    ('prusa-mini-pl',[31],'Verified correct','Screenshot legend','All 12 published Polish legend entries and source caption remain; screenshot labels are not translated.'),
    ('prusa-mini-pl',[31],'Not safely representable as text','Screenshot positions','English raster UI and spatial callout endpoints are not transcribed.'),
    ('prusa-mini-pl',[44],'Corrected and verified','Sheet table and selected shared notes','Usage/risk cells carry row/column labels; calibration and handling notes repeated; warranty and double-sided property remain primary-only.'),
    ('prusa-mmu3-en',[22],'Corrected and verified','Two numbered procedures','Separate 2.5/2.6 sequences; straight-end note repeated only for reviewed 2.6 instructions.'),
    ('prusa-mmu3-en',[40],'Verified correct','Purge matrix','All six source rows and Color/Unloaded/Loaded context retained with surrounding volume units.'),
    ('prusa-mmu3-en',[40],'Not safely representable as text','Wipe-to-infill photograph','Photo-only relationships remain visual dependencies.'),
]
for _sid,_page in [('prusa-mk4s-en',42),('prusa-mk4-de',43),('prusa-xl-de',46)]:
    REVIEW_CASES.extend([
        (_sid,[_page],'Verified correct','Fourteen-item legend','All 14 published explanations retain order and source wording, matching the original R1 case.'),
        (_sid,[_page],'Not safely representable as text','Raster interface callouts','Raster UI positions/arrow endpoints are not added to text; original page remains available.')])


def verify(root,corpus,r1,expected=None):
    inventory=root/'r2-integrity-inventory.json'
    if expected and sha(inventory)!=expected:raise ValueError('R2 inventory trust anchor mismatch')
    before=json.loads((root/'input-integrity.json').read_text(encoding='utf-8'))
    if guard_inputs(corpus,r1,root,record=False)!=before:raise ValueError('Accepted/R1 anchors changed')
    records=json.loads(inventory.read_text(encoding='utf-8'))['files']
    for record in records:
        path=(root/record['path']).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size!=record['bytes'] or sha(path)!=record['sha256']:
            raise ValueError('R2 file mismatch: '+record['path'])
    expected_paths={r['path'] for r in records}|{inventory.name}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual!=expected_paths:raise ValueError('Unexpected or missing R2 paths: '+str(sorted(actual^expected_paths)))
    # Inputs must also have no unrecorded additions.
    for folder,name in [(corpus,'integrity-inventory.json'),(r1,'r1-integrity-inventory.json')]:
        names={r['path'] for r in json.loads((folder/name).read_text(encoding='utf-8'))['files']}|{name}
        actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        if actual!=names:raise ValueError('Input inventory path set changed: '+str(folder))
    return dict(verified=True,r2_files=len(records),accepted_files=before['accepted']['files_verified'],
                r1_files=before['r1']['files_verified'],inventory_sha256=sha(inventory),scope='Byte integrity only; no semantic certification')


def package(root,corpus,r1,repo):
    guard_inputs(corpus,r1,root,record=False)
    audit=json.loads((root/'automated-audit.json').read_text(encoding='utf-8'))
    inputs=json.loads((root/'input-integrity.json').read_text(encoding='utf-8'))
    tests=(root/'isolated-tests.txt').read_text(encoding='utf-8')
    passed=re.search(r'(\d+) passed in ([\d.]+)s',tests)
    if not passed or re.search(r'\b(?:failed|ERROR)\b',tests):raise ValueError('Passing isolated test log required')
    decisions=[dict(source_id=sid,page=page,outcome=outcome,component=component,observation=observation,
                    review_scope='Visual source comparison with generated Markdown; component only, not page certification')
               for sid,pages,outcome,component,observation in REVIEW_CASES for page in pages]
    dump(root/'visual-review-decisions.json',dict(reviewer='Codex agent; not independent human certification',date='2026-11-11',decisions=decisions))
    selected=sorted({(d['source_id'],d['page']) for d in decisions})
    html=['<!doctype html><meta charset="utf-8"><title>R2 local candidate review</title>',
          '<style>body{font:16px system-ui;margin:2em}section{border-top:2px solid #888;margin-top:2em}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1em}img{width:100%;position:sticky;top:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px monospace}summary{cursor:pointer}</style>',
          '<h1>R2 candidate review — local research only</h1><p>Component decisions do not certify pages. Source graphics remain unresolved where marked. Right panel is exact candidate Markdown including derived repetitions.</p>']
    for sid,page in selected:
        mapping=json.loads((root/'maps'/f'{sid}.json').read_text(encoding='utf-8'))
        candidate=(root/'candidates'/f'{sid}.md').read_text(encoding='utf-8')
        ranges=[p for p in mapping['primary'] if p['page']==page]
        excerpt=''.join(candidate[p['start']:p['end']] for p in ranges)
        html.extend([f'<section id="{sid}-{page}"><h2>{sid} / PDF page {page}</h2>',
                     '<ul>'+''.join('<li>'+escape(d['component']+': '+d['outcome']+'. '+d['observation'])+'</li>' for d in decisions if (d['source_id'],d['page'])==(sid,page))+'</ul>',
                     f'<div class="pair"><div><img loading="lazy" src="page-renders/{sid}/page-{page:03d}.png" alt="Original PDF page"></div><pre>'+escape(excerpt or '[No source content on this blank page]')+'</pre></div></section>'])
    (root/'review.html').write_text('\n'.join(html),encoding='utf-8')
    with (root/'unresolved-critical-high-pages.csv').open('w',encoding='utf-8',newline='') as file:
        writer=csv.writer(file);writer.writerow(['source_id','pdf_page','severity','flags','component_review_exists','whole_page_certified'])
        for p in audit['page_records']:
            if p['severity'] in ('Critical','High'):
                writer.writerow([p['source_id'],p['page'],p['severity'],';'.join(f['reason'] for f in p['flags']),(p['source_id'],p['page']) in selected,False])
    source=json.loads((corpus/'source-manifest.json').read_text(encoding='utf-8'))
    manuals=[]
    for m in audit['manuals']:
        u=next(u for u in source['source_units'] if u['id']==m['id'])
        manuals.append({**m,**{k:u[k] for k in ('revision','language','url','original_path','original_sha256','normalized_sha256','license')},
                        'source_root_relative':'../'+corpus.name,'map_path':f'maps/{m["id"]}.json','admitted':False})
    reproduction=['tools/corpus/prusa_pdf_r2.py','tools/corpus/audit_prusa_r2.py','tools/corpus/finalize_prusa_r2.py',
                  'tools/corpus/prusa_pdf_remediation.py','tests/evaluation/test_prusa_pdf_r2.py']
    for relative in reproduction:
        target=root/'reproduction-tools'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/relative,target)
    dependencies=['laew/rag/knowledge_base.py','laew/rag/markdown_chunker.py','laew/rag/contextual_chunker.py','scripts/run_isolated.py']
    code_hashes={p:sha(repo/p) for p in reproduction+dependencies if (repo/p).is_file()}
    manifest=dict(task='3C.2A-R2',date='2026-11-11',status='candidates-only-not-admitted-not-frozen',
                  source_root_relative='../'+corpus.name,r1_root_relative='../'+r1.name,input_integrity=inputs,
                  tools={'python_extraction':'3.12.14','pdfplumber':'0.11.9','poppler':'26.07.0','python_audit':'3.14.7'},
                  transformations=['Existing PDF text and geometry; no OCR or generated descriptions','Source font headings, bounded verbatim callouts, conservative reviewed dependency repetition',
                                   'Every table cell retained; derived row/column context repeated','Full source page renders and explicit unresolved visual markers',
                                   'Derived unique H6 packet boundaries, unchanged size 1000 and legacy overlap 200'],
                  manuals=manuals,severity_counts=audit['severity_counts'],visual_review={'pages':len(selected),'component_decisions':len(decisions),'whole_page_certifications':0},
                  tests={'passed':int(passed[1]),'seconds':float(passed[2]),'log':'isolated-tests.txt','runner':'scripts/run_isolated.py'},
                  code_sha256=code_hashes,postgreSQL_WAL_commit_preserved='220b5263dbb71bbe2966c6d47c0c456c14ed4e48',
                  limitations=['Automated glyph/cell checks do not establish semantic completeness','Reviewed dependency coverage is partial; unreviewed proposals are not broadcast',
                               'No independent human certification','Source text and page renders remain local; no handbook redistribution grant established'])
    dump(root/'candidate-manifest.json',manifest)
    readme='''# R2 local candidates — not admitted or frozen

All six full Markdown candidates are in `candidates/`; 418 original renders in `page-renders/`.
Use `review.html` for exact candidate excerpts beside original pages. Component decisions do not certify whole pages.
`inspection-queue.csv` lists all 418 pages; `unresolved-critical-high-pages.csv` lists exact unresolved priority pages.
`candidate-manifest.json` records hashes, unchanged source revisions, tools, tests and provenance.
`maps/` records source line ownership, primary ranges, full dependency IDs and short alias mappings.
Source glyph geometry and structured blocks are retained independently; no raster-only content is invented.

## Offline integrity verification (read only)

From the LAEW checkout with its existing Python environment:

```powershell
python -B tools/corpus/finalize_prusa_r2.py --verify --output 'C:\\Users\\korne\\LAEW-corpus\\stage-2b2-real-world-20261111-r2-v1' --expected-inventory-sha <SHA256-from-repository-report>
```

No downloads, extraction, embedding, indexing or admission occurs. `--verify` also checks accepted and R1 inventories and input anchors.

## Reproduction

Use a NEW, separate output path; do not overwrite this packaged candidate. Run `prusa_pdf_r2.py` with `--corpus`, `--r1`, `--output`, and `--extract --compile --render` under the bundled Python with pdfplumber 0.11.9; pdftoppm 26.07.0 must be on PATH.
Then run `audit_prusa_r2.py` with the same three paths under the existing LAEW Python environment.
Code snapshots and hashes are under `reproduction-tools/` and the candidate manifest. The production chunkers remain supplied by the pinned local checkout hashes; no new software is installed.

## Diagnostic history

`heading-association-failure-v1.json` and `contract-stop.json` are superseded experiments: missing subsection headings and overly broad chapter associations caused false capacity alarms. `contract-status.json` is the final capacity assessment for reviewed dependencies. No required source warning was shortened to fit.
`automated-audit-v1-markup-false-positives.json` predates the fix for source table `<br>` normalization. `automated-audit.json` is authoritative for this candidate.
The retained preflight record precedes full conversion; its `full_manual_conversion_performed=false` describes that preflight only.

## Boundaries

Local research storage only. No redistribution authorization for Prusa handbooks was established; do not publish these candidates, page renders or copied source text. Accepted corpus and R1 are immutable inputs. Mixed PL/EN Git sections and the pinned PostgreSQL WAL commit are untouched. No freeze, admission, questions, evidence labels, retrieval or model inference occurred.
'''
    (root/'README.md').write_text(readme,encoding='utf-8')
    inventory=dict(algorithm='SHA-256',files=[dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                       for p in sorted(root.rglob('*')) if p.is_file() and p.name!='r2-integrity-inventory.json'])
    dump(root/'r2-integrity-inventory.json',inventory)
    result=verify(root,corpus,r1)
    # Metadata only in Git: no manual text, PDF or page images.
    export={**manifest,'inventory_verification':result,'page_records':audit['page_records'],
            'visual_decisions':decisions,'totals':{k:audit[k] for k in ('total_characters','total_primary_characters','total_dependency_repetition_characters','total_chunks')}}
    dump(repo/'docs/reports/prusa-pdf-r2-20261111-audit.json',export)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--expected-inventory-sha')
    ap.add_argument('--corpus',type=Path,default=Path(r'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111'))
    ap.add_argument('--r1',type=Path,default=Path(r'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r1'))
    args=ap.parse_args()
    if args.verify:print(json.dumps(verify(args.output,args.corpus,args.r1,args.expected_inventory_sha),indent=2))
    else:package(args.output,args.corpus,args.r1,Path(__file__).resolve().parents[2])
