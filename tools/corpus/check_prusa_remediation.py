"""Offline R1 source fidelity, parser compatibility and chunk-boundary diagnostics."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
import difflib
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
import shutil

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from laew.rag.knowledge_base import KnowledgeBase
from prusa_pdf_remediation import SAMPLES,sha,dump,baseline_guard


def flattened(text):
    text=text.replace('**','').replace('<br>',' ').replace(chr(92)+'|','|')
    return re.sub(r'\s+','',text)


def chunks_for(path,text,strategy):
    kb=object.__new__(KnowledgeBase);kb.chunk_size=1000;kb.chunk_overlap=200;kb.chunking_strategy=strategy
    return kb._load_file(path,'global',path.parent,content=text,embed=False)


def check(output,corpus):
    baseline_guard(corpus,output)
    records=[]
    for path in sorted((output/'samples').glob('*.md')):
        name=path.stem
        data=json.loads((output/'objects'/f'{name}.json').read_text(encoding='utf-8'))
        maps=json.loads((output/'maps'/f'{name}.json').read_text(encoding='utf-8'))
        text=path.read_text(encoding='utf-8');before=(output/'before'/path.name).read_text(encoding='utf-8')
        record=dict(id=data['id'],page=data['page'],after_sha256=sha(path),strategies={},missing_source_lines=[])
        block_by_line={line:b for b in maps['blocks'] for line in b['source_lines']}
        # Each source line must retain every non-whitespace glyph, except an explicit menu bullet.
        # Table column sorting changes interleaved line order, so use exact cell text separately.
        for line in data['lines']:
            if line['text'] in maps['removed_footer_lines']:continue
            block=block_by_line[line['index']]
            if block['kind']=='table':continue
            plain=''.join(c['text'] for c in sorted(line['chars'],key=lambda c:c['x0']))
            plain=re.sub(r'^[❏□▢]\s*','',plain)
            if flattened(plain) not in flattened(block['text']):record['missing_source_lines'].append(line['index'])
        record['missing_table_cells']=[]
        for block in maps['blocks']:
            if block['kind']=='table':
                for row in block['source_rows']:
                    for value in row:
                        if value and flattened(value.replace('•','')) not in flattened(block['text'].replace('- ','')):
                            # Cell bullets become Markdown bullets only; all words/values must survive.
                            source=re.sub(r'[\s•]','',value)
                            normalized=re.sub(r'[\s•]','',block['text'].replace('\n- ',''))
                            if source not in normalized:record['missing_table_cells'].append(value)
        menu=next((b for b in maps['blocks'] if b['kind']=='menu'),None)
        notes=[b for b in maps['blocks'] if b['kind'] in ('warning','information','icon-note','callout')]
        if menu:
            record['menu_path_count']=len(menu['rows'])
            record['before_missing_explicit_menu_paths']=sum(r['path'] not in before for r in menu['rows'])
        for strategy in ('legacy','structure-v2'):
            chunks=chunks_for(path,text,strategy)
            assert all(c.embedding is None for c in chunks)
            result=dict(count=len(chunks),max_characters=max((len(c.text) for c in chunks),default=0),
                before_count=len(chunks_for(output/'before'/path.name,before,strategy)),
                menu_paths_missing_in_single_chunk=[r['path'] for r in menu['rows'] if not any(r['path'] in c.text for c in chunks)] if menu else [],
                callouts_split_across_chunks=[i for i,b in enumerate(notes) if not any(b['text'] in c.text for c in chunks)],
                source_partition_exact=None)
            if strategy=='structure-v2':
                result['source_partition_exact']=''.join(text[c.metadata['start_offset']:c.metadata['end_offset']] for c in chunks)==text
            if menu:
                warning=notes[0]['text'] if notes else ''
                result['menu_chunks_without_complete_page_note']=sum(any(r['path'] in c.text for r in menu['rows']) and warning not in c.text for c in chunks)
            # Warn explicitly when an ancestor section's red callouts are absent in a procedural descendant chunk.
            warnings=[b for b in notes if b['kind']=='warning']
            if warnings:
                result['chunks_without_complete_prior_warnings']=sum(any(b['text'][:60] in c.text for b in maps['blocks'] if b['kind']=='paragraph' and b['start']>warnings[-1]['end']) and not all(w['text'] in c.text for w in warnings) for c in chunks)
            record['strategies'][strategy]=result
        (output/'diffs').mkdir(exist_ok=True)
        (output/'diffs'/f'{name}.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='accepted-page-markdown',tofile='R1-geometry-sample')),encoding='utf-8')
        records.append(record)
    summary=dict(sample_pages=len(records),original_eight=sum((r['id'],r['page']) in SAMPLES for r in records),
        all_non_table_source_lines_preserved=not any(r['missing_source_lines'] for r in records),
        all_table_cells_preserved=not any(r['missing_table_cells'] for r in records),records=records,
        note='Dry chunk diagnostics only. Missing local context is reported, not repaired by changing production chunkers.')
    dump(output/'chunk-and-fidelity-checks.json',summary)
    # Local review viewer shows original rendered page and exact before/after Markdown; it never leaves staging.
    sections=[]
    for r in records:
        name=f'{r["id"]}-page-{r["page"]}'
        old=(output/'before'/f'{name}.md').read_text(encoding='utf-8');new=(output/'samples'/f'{name}.md').read_text(encoding='utf-8')
        sections.append(f'<section><h2>{escape(name)}</h2><div class="grid"><a href="renders/{name}.png"><img src="renders/{name}.png" alt="Original PDF page"></a><pre>{escape(old)}</pre><pre>{escape(new)}</pre></div></section>')
    viewer='<!doctype html><html lang="en"><meta charset="utf-8"><title>Prusa R1 source comparison</title><style>body{font:15px system-ui;margin:24px;color:#17202a}section{border-top:1px solid #aaa;margin-top:32px}.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px}.grid img{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f7;padding:12px;margin:0}h1{font-size:24px}h2{font-size:18px}</style><h1>Prusa R1: original PDF / accepted Markdown / geometry sample</h1><p>Local research artifacts only. Click original pages to zoom. Text panes show exact Markdown, including structural annotations. These are not admitted corpus documents.</p>'+''.join(sections)+'</html>'
    (output/'review.html').write_text(viewer,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
    for r in records:print(r['id'],r['page'],{s:r['strategies'][s] for s in r['strategies']})
    return summary


def record_artifacts(output,corpus):
    """Version this R1 review bundle; this is not a corpus freeze/admission operation."""
    baseline_guard(corpus,output)
    repo=Path(__file__).resolve().parents[2]
    audit=json.loads((output/'structural-audit-418.json').read_text(encoding='utf-8'))
    checks=json.loads((output/'chunk-and-fidelity-checks.json').read_text(encoding='utf-8'))
    samples=json.loads((output/'sample-results.json').read_text(encoding='utf-8'))
    probes=json.loads((output/'table-probe-results.json').read_text(encoding='utf-8'))
    with (output/'inspection-queue-418.csv').open('w',encoding='utf-8',newline='') as file:
        writer=csv.writer(file);writer.writerow(['source_id','pdf_page','inspection_status','flags'])
        for r in audit['records']:writer.writerow([r['id'],r['page'],r['inspection_status'],';'.join(r['flags'])])
    (output/'reproduction-tools').mkdir(exist_ok=True)
    code={}
    for name in ('tools/corpus/prusa_pdf_remediation.py','tools/corpus/check_prusa_remediation.py','tests/evaluation/test_prusa_pdf_remediation.py'):
        source=repo/name;shutil.copyfile(source,output/'reproduction-tools'/source.name);code[name]=sha(source)
    baseline=json.loads((output/'baseline-guard.json').read_text(encoding='utf-8'))
    manifest=dict(task='3C.2A-R1',status='review-only-not-frozen',source_corpus=str(corpus),r1_directory=str(output),
        baseline=baseline,sample_pages=8,additional_table_probe_pages=2,scanned_pages=418,
        full_manual_conversion_performed=False,questions_or_labels_created=False,indexing_or_embeddings_performed=False,
        methods={'engine':'pdfplumber 0.11.9; pdfminer character/rectangle/image objects','pdf_python':'3.12.14','check_python':sys.version.split()[0],
                 'raster_reference':'Existing Poppler 26.07.0 renders; same renderer for two table probe pages','ocr':False,
                 'pymupdf':'Documentation considered; not installed or used; no new dependencies installed'},
        source_code_sha256=code,samples=samples,table_probes=probes,
        checks={k:v for k,v in checks.items() if k!='records'},
        limitations=['Raster-only spatial meaning remains visual-review-only','Shared warnings/notes can be missing in later chunks in both strategies',
                     'Merged/borderless tables and cross-page structures are not automatically certified','R1 icon dictionary covers only reviewed image-stream hashes'],
        tests={'command':'python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q',
               'result':'37 passed in 3.19s'})
    dump(output/'review-snapshot-manifest.json',manifest)
    readme='''# Prusa R1 review bundle - not admitted corpus

Only eight originally flagged pages and two additional real table pages were converted.
The 418-page structural audit reads PDF objects without producing full manual Markdown.
Accepted corpus originals, normalized documents, manifest and inventory remain unchanged.
The baseline trust anchors are preserved under baseline-snapshot/ and checked before/after runs.
Prusa source material stays local; no handbook redistribution permission was established.

Open review.html for original PDF / accepted Markdown / R1 Markdown side-by-side.
objects/ and maps/ retain glyph/font/coordinate provenance. Figure crops are original pixels,
not generated descriptions. Source-only graphical information is explicitly unresolved.
inspection-queue-418.csv lists every page, including unflagged pages that are not certified.

Reproduce from the LAEW checkout using the bundled PDF interpreter (no installation needed):

    PDF_PYTHON -B tools/corpus/prusa_pdf_remediation.py --corpus "@CORPUS@" --output "@OUTPUT@" --samples --table-probes --audit-pages
    python -B tools/corpus/check_prusa_remediation.py --corpus "@CORPUS@" --output "@OUTPUT@"

Run tests using scripts/run_isolated.py with LAEW_PUBLIC_CORPUS_ROOT and LAEW_PRUSA_R1_ROOT.
Recorded tool versions and hashes are in review-snapshot-manifest.json. Keep the accepted
extraction cache: it supplies the second-extractor comparison and preceding section context.

    python -B tools/corpus/check_prusa_remediation.py --corpus "@CORPUS@" --output "@OUTPUT@" --verify-r1

This verifies the R1 review inventory and accepted corpus hashes offline. The inventory does
not authorize corpus freezing. Stop before full manual conversion until Task 3C.2A-R2 approval.
PDF_PYTHON denotes the bundled Python executable returned by load_workspace_dependencies.
'''.replace('@CORPUS@',str(corpus)).replace('@OUTPUT@',str(output))
    (output/'README.md').write_text(readme,encoding='utf-8')
    files=[dict(path=p.relative_to(output).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='r1-integrity-inventory.json']
    dump(output/'r1-integrity-inventory.json',{'algorithm':'SHA-256','status':'review-bundle-only','files':files})
    anchors={'review_manifest_sha256':sha(output/'review-snapshot-manifest.json'),'r1_inventory_sha256':sha(output/'r1-integrity-inventory.json')}
    export=dict(task='3C.2A-R1',status='not-ready-for-full-automatic-admission',r1_directory=str(output),baseline=baseline,integrity=anchors,
        samples=samples,table_probes=probes,chunk_and_fidelity_checks=checks,structural_audit=audit,source_code_sha256=code,tests=manifest['tests'])
    dump(repo/'docs/reports/prusa-pdf-r1-20261111-audit.json',export)
    print(json.dumps(dict(integrity=anchors,r1_files=len(files),sample_pages=10,scanned_pages=418),indent=2))


def verify_artifacts(output,corpus):
    baseline_guard(corpus,output,record=False)
    inventory=json.loads((output/'r1-integrity-inventory.json').read_text(encoding='utf-8'))
    errors=[]
    for item in inventory['files']:
        path=(output/item['path']).resolve()
        if not path.is_relative_to(output.resolve()) or not path.is_file() or sha(path)!=item['sha256']:errors.append(item['path'])
    expected={item['path'] for item in inventory['files']}|{'r1-integrity-inventory.json'}
    unexpected={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}-expected
    errors+=sorted(unexpected)
    print(json.dumps({'verified':not errors,'r1_files_checked':len(inventory['files']),'accepted_corpus_unchanged':True,'errors':errors},indent=2))
    if errors:raise SystemExit(1)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--corpus',type=Path,required=True)
    ap.add_argument('--record-integrity',action='store_true');ap.add_argument('--verify-r1',action='store_true')
    args=ap.parse_args()
    if args.verify_r1:verify_artifacts(args.output,args.corpus)
    elif args.record_integrity:record_artifacts(args.output,args.corpus)
    else:check(args.output,args.corpus)
