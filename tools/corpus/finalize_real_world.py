"""Record acquisition QA, reproducibility files, and a metadata-only repository export."""
from __future__ import annotations
import argparse
from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess

from acquire_real_world import safe_root,sha
from audit_real_world import audit
from verify_corpus import inventory,verify


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',required=True);args=ap.parse_args()
    root=safe_root(args.root);repo=Path(__file__).resolve().parents[2]
    manifest=json.loads((root/'source-manifest.json').read_text(encoding='utf-8'))
    language_candidates=[]
    for u in manifest['source_units']:
        u['verification_scope']='Acquisition, source fidelity, dry parser compatibility only. No questions, labels, embeddings, indexes or retrieval.'
        u['retrieval_date']=u['retrieved_at'][:10]
        if u['family']=='prusa':
            path=root/u['extraction']['layout_and_independent_extraction'];data=json.loads(path.read_text(encoding='utf-8'))
            data['original_sha256']=u['original_sha256'];write(path,data)
            u['printed_revision_source']='PDF page 2, preserved verbatim in extraction sidecar'
            u['firmware_pin']='Not one fixed firmware release: source instructs updating to the then-current firmware. Keep handbook date/product applicability; do not assume current firmware compatibility.'
            u['extraction']['low_agreement_pages']=[p['page'] for p in data['page_records'] if p['token_agreement']<.95]
            if u['id']=='prusa-xl-de':u['extraction']['visually_confirmed_blank_pages']=[7]
            u['language_review']={'primary':u['language'],'scope':'Full extracted text with sampled PDF visual QA; original UI screenshots include English labels even in PL/DE handbooks.',
                'untranslated_passages':([{'pdf_page':2,'text':'IMPORTANT INFORMATION REGARDING ORIGINAL PRUSA MK3.9:','language':'en'}] if u['id']=='prusa-mk4-de' else [])}
        elif u['family']=='progit':
            u['edition']='Second edition'
            u['source_path_attribution_url']=u['url']
            if u['language']=='pl':
                ranges={'progit-config-pl':{'from_line':411,'through_end':True},'progit-submodules-pl':{'from_line':199,'through_end':True}}
                u['language_review']={'primary':'pl','untranslated_source_ranges':([ranges[u['id']]] if u['id'] in ranges else []),
                    'neutral_content':'English command output and code are not counted as translated prose',
                    'translation_drift':'The Polish first-time setup predates several EN/DE additions, including default-branch-name setup; no material was backfilled or translated.'}
            u['extraction']['transformations']+=['Remove non-published AsciiDoc index macros and passthrough delimiters; retain text','Resolve available cross-references using official rendered snapshot links; preserve unresolved upstream reference text visibly']
            if u['language']!='en':
                text=(root/u['original_path']).read_text(encoding='utf-8');fence=False
                import re
                for i,line in enumerate(text.splitlines(),1):
                    if line=='----':fence=not fence;continue
                    if fence:continue
                    words=re.findall(r'\b[a-z]+\b',re.sub(r'`[^`]+`','',line).lower())
                    count=sum(w in {'the','you','your','this','these','when','will','with','that','which','would','because','have','has','are','and','can'} for w in words)
                    if count>=4 and len(words)>12:language_candidates.append({'id':u['id'],'source_line':i,'review':'Expected fallback in reviewed untranslated source range'})
    write(root/'verification/language-screening.json',{'method':'English function-word screening outside source listings, plus agent inspection of source transitions','candidates':language_candidates,
        'human_bilingual_certification':False,'user_decision':'Retain complete mixed Polish sections, label passage languages, and revise PL assumptions (2026-11-11).'})
    qa={'reviewer':'Codex agent; no generative model calls or OCR tools used','renderer':'Poppler pdftoppm 26.07.0, PNG, scale-to 1700',
        'visual_samples':[
            {'id':'prusa-mk4s-en','page':42,'finding':'Screenshot spatial callouts missing from plain text; list labels retained.'},
            {'id':'prusa-mk4-de','page':43,'finding':'Same screenshot callout issue; English UI labels are visible in German handbook.'},
            {'id':'prusa-mini-pl','page':31,'finding':'English UI screenshot with Polish labels; numbered spatial correspondence is not encoded in Markdown.'},
            {'id':'prusa-mk3s-pl','page':35,'finding':'Nested LCD menu and icon relationships flattened in plain text; temperatures such as PLA 215/60 retained, menu hierarchy not certified.'},
            {'id':'prusa-mmu3-en','page':22,'finding':'Procedure prose and numeric steps present; orange information-box boundary/icon absent from text.'},
            {'id':'prusa-xl-de','page':23,'finding':'Red warning boxes and image-dependent orange alignment marks absent from text-only representation.'},
            {'id':'prusa-xl-de','page':7,'finding':'Visually blank original page; zero text agreement is not a missing technical page.'},
            {'id':'prusa-xl-de','page':46,'finding':'Screenshot callouts require image context; explanatory list retained.'}],
        'decision':'All six manuals retained in full but unsuitable for freeze until image/table/hierarchy/warning association extraction is repaired and checked. Review samples do not certify the other PDF pages.'}
    write(root/'verification/pdf-visual-review.json',qa)
    failures=[
        {'request':'https://api.github.com/repos/progit/progit2-pl/commits/HEAD','status':404,'resolution':'Official book source link identifies progit2-pl/progit2-pl; same requested Polish translation, not a substitute.'},
        {'request':'https://git-scm.com/book/de/v2/Erste-Schritte-Git-erstmalig-einrichten','status':404,'resolution':'Official chapter navigation gives Erste-Schritte-Git-Basis-Konfiguration.'},
        {'request':'https://git-scm.com/book/de/v2/Git-anpassen-Git-Konfiguration','status':404,'resolution':'Official chapter navigation gives Git-einrichten-Git-Konfiguration.'},
        {'request':'PostgreSQL 11/12 configure.ac at pinned tags','status':404,'resolution':'Historical upstream uses configure.in; exact tagged files acquired.'},
        {'request':'Sandboxed public HTTPS download','status':'DNS/network restriction','resolution':'Authorized public download repeated through escalation; no source unavailable.'}]
    write(root/'verification/acquisition-failures.json',failures)
    (root/'reproduction-tools').mkdir(exist_ok=True)
    tool_hashes={}
    for path in sorted((repo/'tools/corpus').glob('*.py')):
        data=path.read_bytes();(root/'reproduction-tools'/path.name).write_bytes(data);tool_hashes[path.name]=sha(data)
    manifest['normalization_code_sha256']=tool_hashes
    manifest['reviewed_laeW_files_sha256']={name:sha((repo/name).read_bytes()) for name in [
        'laew/rag/knowledge_base.py','laew/rag/markdown_chunker.py','laew/rag/contextual_chunker.py',
        'laew/rag/obsidian.py','laew/eval/rag_baseline.py','scripts/run_isolated.py',
        'docs/reports/STAGE_2B2_REAL_WORLD_RAG_BENCHMARK_SPEC_20261111.md']}
    manifest['normalization_environment']={'python':platform.python_version(),'html2text':importlib.metadata.version('html2text'),
        'pdf_python':next(u['extraction']['tools']['python'] for u in manifest['source_units'] if u['family']=='prusa'),'pypdf':'6.21.4','pdfplumber':'0.11.9','poppler':'26.07.0','encoding':'UTF-8','line_endings':'LF'}
    manifest['integrity_command']='python -B tools/corpus/verify_corpus.py --root '+str(root)
    manifest['source_count']=24
    write(root/'source-manifest.json',manifest)
    result=audit(root);write(root/'verification/content-audit.json',result)
    plan=[]
    for log in sorted(root.rglob('*.http.json')):
        record=json.loads(log.read_text(encoding='utf-8'));original=Path(str(log)[:-10])
        assert original.is_file(),original
        assert sha(original.read_bytes())==record['sha256'],original
        plan.append(dict(path=original.relative_to(root).as_posix(),url=record['requested_url'],sha256=record['sha256']))
        # Preserve acquisition facts, excluding irrelevant public cookie/session/cache values.
        record['headers']={k:v for k,v in record['headers'].items() if k.lower() in {'content-type','content-length','content-encoding','etag','last-modified','date','server','location'}}
        write(log,record)
    write(root/'download-plan.json',plan)
    instructions='''# Task 3C.2A public corpus staging

This directory contains unchanged public source originals and derived local research copies.
Do not redistribute Prusa handbooks: no document-specific redistribution grant was identified.
Pro Git is CC BY-NC-SA 3.0. PostgreSQL permits redistribution with its notice.
The corpus is NOT FROZEN. Six PDF normalizations have explicit admission defects.

From the LAEW checkout, verify all recorded bytes without downloading or using models:

    python -B tools/corpus/verify_corpus.py --root "STAGING_ROOT"

For an empty destination, re-fetch exact URLs and reject any changed bytes:

    python tools/corpus/acquire_real_world.py --root "NEW_EXTERNAL_ROOT" --replay-plan "STAGING_ROOT/download-plan.json"

Git raw URLs are commit-pinned. Mutable publisher HTML/PDF URLs can change; a mismatch is
an intentional hard failure. Archived local originals, maps and scripts remain authoritative.
Reacquisition restores downloaded source bytes, not the derived metadata/HTTP retrieval times.

To regenerate normalization from the archived inputs, use the recorded Python dependencies:

    PDF_PYTHON reproduction-tools/extract_pdfs.py --root "STAGING_ROOT"
    python reproduction-tools/normalize_real_world.py --root "STAGING_ROOT"

The bundled PDF interpreter already supplied pypdf and pdfplumber; no packages/models were installed.
Audit and pytest require the LAEW checkout. Never invoke a loader with embedding enabled.
Inventory writes are a maintenance operation; use --write-inventory only after an intentional,
reviewed change, then compare and update the metadata-only repository export.
'''.replace('STAGING_ROOT',str(root))
    (root/'README.md').write_text(instructions,encoding='utf-8')
    inventory(root)
    checked=verify(root);assert checked['verified'],checked
    keys=('id','family','publisher','canonical_url','url','language','language_status','revision','printed_revision_date','hardware','applicable_versions','retrieved_at','retrieval_date',
          'repository','commit','release_tag','released_baseline_tag','source_path','upstream_path','original_path','original_sha256','original_bytes','rendered_path','rendered_sha256',
          'normalized_path','normalized_sha256','normalized_bytes','normalized_characters','body_characters','body_offset','license','extraction','language_map','language_characters','language_review','verification_status','warnings')
    export={'schema':manifest['schema'],'task':'3C.2A','staging_root':str(root),'readiness':manifest['readiness'],'integrity':checked,
        'metrics':{k:v for k,v in result.items() if k not in ('postgresql','progit')},
        'normalization_code_sha256':tool_hashes,'reviewed_laeW_files_sha256':manifest['reviewed_laeW_files_sha256'],'environment':manifest['normalization_environment'],
        'source_units':[{k:u[k] for k in keys if k in u} for u in manifest['source_units']]}
    export_path=repo/'docs/reports/real-world-corpus-20261111-manifest.json';write(export_path,export)
    print(json.dumps({'integrity':checked,'staging_bytes':sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
        'body_characters':result['body_characters'],'chunks':result['chunks'],'metadata_export':str(export_path)},indent=2))


if __name__=='__main__':main()
