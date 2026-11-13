"""R3C risk/provenance packaging and offline verification; never admits sources."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import platform
import re
import shutil

from regenerate_prusa_r3c import load,write,digest,verify_inputs,R3B_SHA,WAL_COMMIT


def prepare_review(out,r2,r3b):
    manifest=load(out/'source-manifest.json');maps={u['id']:load(out/u['source_map']) for u in manifest['source_units'] if u['family']=='prusa'}
    units={u['id']:u for u in manifest['source_units']}
    availability=load(out/'availability-register.json')
    for region in availability:
        records={r['id']:r for r in maps[region['source_id']]['records']}
        region['source_ranges']=[{k:records[i][k] for k in ('id','page','start','end')} for i in region['source_block_ids']]
        region['normalized_path']=units[region['source_id']]['normalized_path'];region['admission_status']='not-admitted'
    write(out/'availability-register.json',availability)
    gates=load(r3b/'triage-results.json')['mandatory_human_review_pages']
    for gate in gates:
        sid,p=gate['source_id'],gate['page'];mapping=maps[sid];r=next((a for a in availability if (a['source_id'],a['page'])==(sid,p)),None)
        ids=set(r['source_block_ids']) if r else {b['id'] for b in mapping['source_blocks'] if b['page']==p and b['kind'] in ('table','figure')}
        gate['source_ranges']=[{k:b[k] for k in ('id','page','start','end')} for b in mapping['records'] if b['id'] in ids]
        gate.update(status='mandatory-human-review-pending',human_certified=False,normalized_path=units[sid]['normalized_path'])
    write(out/'mandatory-human-review-gates.json',gates)
    risk=load(out/'inherited-r3b/outstanding-risk-register.json');audit={(p['source_id'],p['page']):p for p in load(out/'structural-audit-418.json')['records']}
    for page in risk:
        sid,p=page['source_id'],page['page'];mapping=maps[sid];ranges=next(pg for pg in mapping['pages'] if pg['page']==p)
        page.update(normalized_path=units[sid]['normalized_path'],start=ranges['start'],end=ranges['end'],source_block_ids=ranges['source_block_ids'],
                    candidate_structural_checks_passed=audit[sid,p]['checks_passed'],semantic_certification=False,admission_status='not-admitted',priority_changed=False)
    write(out/'unresolved-risk-register.json',risk)
    translations={}
    for sid,mapping in maps.items():
        records={b['id']:b for b in mapping['records'] if b['kind']!='derived-availability'}
        for file in sorted((r2/'structured'/sid).glob('*.json')):
            for old in load(file)['blocks']:
                translations[old['id']]=[old['id']] if old['id'] in records else [b['id'] for b in records.values() if b['page']==old['page'] and set(b['source_lines'])&set(old['source_lines'])]
    proposals=load(out/'warning-applicability-unreviewed.json')
    for relation in proposals['relations']:
        relation['r3c_source_block_ids']=translations.get(relation['id'],[])
        relation['r3c_dependency_reference_map']={i:translations.get(i,[]) for i in relation['dependencies']+relation['candidate_dependencies_not_materialized']}
        relation['current_status']='historical-proposal-only; exact applicability must not be inferred from this mapping'
    write(out/'warning-applicability-unreviewed.json',proposals)
    metrics=load(out/'chunking-comparison.json')
    with (out/'per-source-metrics.csv').open('w',encoding='utf-8',newline='') as file:
        names=['source_id','family','characters','body_characters','bytes','normalized_sha256','differing_internal_end_boundaries','legacy_unmatched_payloads','v2_unmatched_payloads','trimmed_payload_sequence_identical']
        for s in ('legacy','structure-v2'):names += [f'{s}_{k}' for k in ('chunks','min','p10','median','p90','p95','max','under_200','delivered_characters','added_overlap_characters','added_context_characters','estimated_delivered_tokens_4chars','limited_context_chunks')]
        writer=csv.DictWriter(file,fieldnames=names);writer.writeheader()
        for unit in metrics['units']:
            row={k:unit[k] for k in ('source_id','family','characters','body_characters','bytes','normalized_sha256')}
            row.update({k:unit['boundary_comparison'][k] for k in ('differing_internal_end_boundaries','legacy_unmatched_payloads','v2_unmatched_payloads','trimmed_payload_sequence_identical')})
            for s in ('legacy','structure-v2'):
                values=unit['chunking'][s]
                for k in ('chunks','delivered_characters','added_overlap_characters','added_context_characters','estimated_delivered_tokens_4chars','limited_context_chunks'):row[f'{s}_{k}']=values[k]
                for k in ('min','p10','median','p90','p95','max','under_200'):row[f'{s}_{k}']=values['sizes'][k]
            writer.writerow(row)
    write(out/'readiness.json',dict(status='candidate-generation-complete-not-admitted-not-frozen',
        inherited_severity_counts={level:sum(p['original_severity']==level for p in risk) for level in ('Critical','High','Medium','Low')},
        uninspected_high=sum(p['original_severity']=='High' and not p['r3b_inspected'] for p in risk),unresolved_regions=len(availability),mandatory_human_review_gates=len(gates),
        structural_failed_pages=metrics['structural_failed_pages'],local_reference_failures=metrics['local_reference_failures'],
        requires_resource_decision=metrics['resource_review_trigger_exceeded'],requires_admission_decision=True,requires_labeling_approval=True,
        warning='Automated consistency does not certify semantic correctness. Sidecars are not automatically delivered to an LLM.'))


def verify(out,accepted,r2,r3a,r3b,expected=None):
    inventory=out/'r3c-integrity-inventory.json'
    if expected and digest(inventory)!=expected:raise ValueError('R3C inventory trust anchor mismatch')
    records=load(inventory)['files']
    for record in records:
        path=(out/record['path']).resolve()
        if not path.is_relative_to(out.resolve()) or not path.is_file() or path.stat().st_size!=record['bytes'] or digest(path)!=record['sha256']:raise ValueError('R3C integrity mismatch: '+record['path'])
    actual={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
    if actual!={r['path'] for r in records}|{inventory.name}:raise ValueError('Unexpected or missing R3C paths')
    current=verify_inputs(accepted,r2,r3a,r3b)
    if current!=load(out/'integrity-before.json'):raise ValueError('Prior corpus changed')
    baseline={u['id']:u for u in load(accepted/'source-manifest.json')['source_units']};units=load(out/'source-manifest.json')['source_units']
    if len(units)!=24 or len({u['id'] for u in units})!=24 or set(baseline)!={u['id'] for u in units}:raise ValueError('Source selection differs')
    for u in units:
        if digest(out/u['original_path'])!=u['original_sha256'] or digest(out/u['normalized_path'])!=u['normalized_sha256']:raise ValueError('Source unit hash mismatch')
        if u['family']!='prusa' and u['normalized_sha256']!=baseline[u['id']]['normalized_sha256']:raise ValueError('One of 18 unchanged units differs')
    if next(u['commit'] for u in units if u['id']=='postgresql-17-runtime-config-wal')!=WAL_COMMIT:raise ValueError('WAL pin changed')
    return dict(verified=True,r3c_files=len(records),units=24,unchanged_text_units=18,inventory_sha256=digest(inventory),prior_inputs=current,
                scope='Offline byte identity and provenance integrity; no semantic admission')


def package(out,accepted,r2,r3a,r3b):
    text=(out/'isolated-tests.txt').read_text(encoding='utf-8');passed=re.search(r'(\d+) passed in ([\d.]+)s',text)
    if not passed or re.search(r'\b(?:failed|ERROR)\b',text):raise ValueError('Passing isolated tests required')
    repo=Path(__file__).resolve().parents[2];manifest=load(out/'source-manifest.json')
    tools=['tools/corpus/regenerate_prusa_r3c.py','tools/corpus/audit_prusa_r3c.py','tools/corpus/finalize_prusa_r3c.py','tests/evaluation/test_prusa_pdf_r3c.py']
    deps=['tools/corpus/review_prusa_r3a.py','tools/corpus/triage_prusa_r3b.py','tools/corpus/prusa_pdf_remediation.py','tools/corpus/prusa_pdf_r2.py','tools/corpus/finalize_prusa_r2.py',
          'tools/corpus/audit_prusa_r2.py','laew/rag/knowledge_base.py','laew/rag/markdown_chunker.py','laew/rag/contextual_chunker.py','scripts/run_isolated.py']
    for name in tools:
        target=out/'reproduction-tools'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/name,target)
    manifest.update(runtime=dict(python=platform.python_version(),input_pdfplumber='0.11.9',input_pdf_python='3.12.14',input_poppler='26.07.0',
        code_sha256={name:digest(repo/name) for name in tools+deps}),tests=dict(passed=int(passed[1]),seconds=float(passed[2]),runner='scripts/run_isolated.py'),
        build_scope='Six complete Prusa source-once candidates and eighteen byte-identical accepted Markdown copies; no admission, freeze, questions, labels, embeddings or retrieval',
        local_license_limit='No Prusa handbook redistribution grant established; PDFs, Markdown, maps, page renders and payload material stay outside Git')
    write(out/'source-manifest.json',manifest)
    after=verify_inputs(accepted,r2,r3a,r3b)
    if after!=load(out/'integrity-before.json'):raise ValueError('Input inventory changed')
    write(out/'integrity-after.json',after)
    (out/'README.md').write_text('''# R3C source-once corpus candidates — not admitted or frozen

`normalized/` contains all 24 source units: six regenerated Prusa manuals and 18 byte-identical Git/PostgreSQL units.
`source-manifest.json` records original/normalized hashes, versions, languages, URLs, tools and license limits.
`maps/` records full-file character offsets, source lines/cells/pages, derived annotation subranges and hash-gated overlays. Blank PDF pages remain represented in page maps and assets.
`assets/prusa-pages/` contains all 418 unchanged original page rasters. Original embedded image pixels remain in the unchanged PDFs; `image-object-register.json` retains all native object/bbox/hash references, including small icons. Full-page renders are access/provenance, not image descriptions.
`applied-repairs.json` records exactly 22 R3B operations over 20 source-matched pages. Explicit one-column list presentation is reconstructed independently of chunk size; uncertain layouts remain unresolved.
`availability-register.json` retains nine precise limits; `mandatory-human-review-gates.json` retains 15 open gates; `unresolved-risk-register.json` carries all 418 unchanged priorities, including 329 uninspected High pages. Structural pass does not clear risk.
`warning-applicability-reviewed.json` contains six rebased R3B scope decisions. Historical proposals are separately marked unverified. No warning is repeated per chunk; sidecars are not automatically delivered to an LLM.
`structural-audit-418.json` lists every tested page and any exact failed check. `per-source-metrics.csv`, `chunking-comparison.json` and `chunk-maps/` record actual unchanged loader outputs. Legacy offsets come from actual-engine tracing; V2 uses native offsets/context spans. No store or embeddings are created.
`representative-review.html` shows representative originals, Markdown and real chunk payloads. It is agent inspection, not independent human certification.

## Reproduction and offline verification

Run `regenerate_prusa_r3c.py` with `--accepted`, `--r2`, `--r3a`, `--r3b`, `--output` pointing to a NEW external output. Then run `audit_prusa_r3c.py --output <R3C> --r2 <R2>` and `finalize_prusa_r3c.py --prepare-review` with all five paths. Run documented isolated tests, saving `isolated-tests.txt`, then use `--package`.
New tool snapshots are under `reproduction-tools/`; pinned helper/runtime hashes are in the manifest and prior preserved workspaces. The initial R3C-v1 draft is retained separately; final v2 renders explicit native bullets as Markdown list markers, with original markers retained in provenance. This presentation correction does not select a strategy or alter technical words.

Offline read-only check: `python -B tools/corpus/finalize_prusa_r3c.py --verify --accepted <accepted> --r2 <R2> --r3a <R3A> --r3b <R3B> --output <R3C> --expected-inventory-sha <repository-report-anchor>`.
The check verifies the complete local inventory and prior corpus chain without downloading, rewriting or indexing anything. Byte integrity does not constitute admission. Do not redistribute restricted source material.
''',encoding='utf-8')
    write(out/'r3c-integrity-inventory.json',dict(algorithm='SHA-256',files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='r3c-integrity-inventory.json']))
    checked=verify(out,accepted,r2,r3a,r3b)
    # Export metadata only. Source paragraphs, chunk payloads and source maps stay local.
    units=[{k:u.get(k) for k in ('id','family','language','revision','commit','source_path','canonical_url','url','original_sha256','normalized_sha256','normalized_path','body_characters','normalized_characters','normalized_bytes','license','candidate_status')} for u in manifest['source_units']]
    export=dict(task='3C.2A-R3C',status='not-admitted-not-frozen',source_units=units,integrity=checked,tests=manifest['tests'],runtime=manifest['runtime'],
        metrics=load(out/'chunking-comparison.json'),readiness=load(out/'readiness.json'),structural_audit=load(out/'structural-audit-418.json'),
        representative_scope_diagnostics=load(out/'representative-scope-diagnostics.json'))
    write(repo/'docs/reports/prusa-pdf-r3c-20261111-verification.json',export)
    shutil.copyfile(out/'per-source-metrics.csv',repo/'docs/reports/prusa-pdf-r3c-20261111-metrics.csv')
    print(json.dumps(checked,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('accepted','r2','r3a','r3b','output'):ap.add_argument('--'+name,type=Path,required=True)
    mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-review',action='store_true');mode.add_argument('--package',action='store_true');mode.add_argument('--verify',action='store_true')
    ap.add_argument('--expected-inventory-sha');a=ap.parse_args()
    if a.prepare_review:prepare_review(a.output,a.r2,a.r3b)
    elif a.package:package(a.output,a.accepted,a.r2,a.r3a,a.r3b)
    else:print(json.dumps(verify(a.output,a.accepted,a.r2,a.r3a,a.r3b,a.expected_inventory_sha),indent=2))
