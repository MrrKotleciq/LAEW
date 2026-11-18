"""Offline-only preparation and verification of the exposed S0/S1 study.

No retrieval, chunk reconstruction, embeddings, credentials or model execution.
Generation-only artifacts are sealed before any scoring material is read.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import copy
import hashlib
import html
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch

from laew.eval import fixed_body_citations as fmt
from laew.eval.complementary_context_study import read, sha, verify_manifest, write
from laew.eval.fixed_body_serialization_study import load_frames
from laew.eval.real_world_answer_plan import INSTRUCTIONS, MODEL, serialize
from laew.rag.evidence_selection import scope_section

REPO = Path(__file__).resolve().parents[2]
PARENT = Path(os.environ.get('LAEW_FIXED_BODY_ROOT', 'laew-fixed-body-citations-v1'))
PREVIOUS = Path(os.environ.get('LAEW_S0_S1_PREVIOUS_ROOT', '.'))
PARENT_SHA = 'ac5054f8fd81fe2dfff39f0575d4387f9600c4c0771dc12e8c03434df8f45450'
SCORER_SHA = '47bbe6152657c336b1d319739569cf4585dc9c3c0f01a6fe8dd8fc0ef30e3d2c'
FAMILY_SLOTS = {
    'P01': 'Small positive Git metadata saving; identity and precedence; multilingual sources.',
    'P02': 'Replacement of the same Prusa sheet type; conditional prerequisites and incomplete evidence.',
    'P03': 'High PostgreSQL metadata overhead; incremental-backup dependencies and fourteen-day retention.',
    'P04': 'Unspecified server version; competing recovery procedures and conditional startup warning.',
    'S04': 'High PostgreSQL metadata overhead; soft-limit explanation and archive-failure condition.',
    'S06': 'Multi-section Prusa firmware procedure; upgraded-model applicability and rollback.',
    'S10': 'Zero metadata-saving Git control; multi-section submodule publication prerequisite.',
    'S11': 'Multi-document, two-device firmware paths and conditional disconnection warnings.',
    'S12': 'PostgreSQL 11-to-17 script migration; session lifetime, metadata and conditional procedure scope.',
    'S13': 'PostgreSQL 11/17 timeline defaults and valid-descendant applicability.',
    'S14': 'Unavailable exact torque; appropriate uncertainty instead of a fabricated number.',
    'S16': 'Unavailable graphical evidence; physical position and symbol cannot be reconstructed.',
}
RISK_DEFINITIONS = {
    'R01': 'Exact immutable revision/hash/applicability contract is sidecar-only; filename is not full source identity.',
    'R02': 'Same rendered filename binds different source revisions in this context; execution blocker.',
    'R03': 'Several PostgreSQL major versions delivered together; keep version-specific procedures separate.',
    'R04': 'Structure-v2 multi-range or synthetic related context; internal gaps are not explicit independent passages.',
    'R05': 'Prusa handbook revision and full hardware/firmware applicability are not explicit in the attribution label.',
    'R06': 'S1 removes navigation identifiers; these can be semantic cues despite not being source-body evidence.',
    'R07': 'Repeated filename/section label for different passages; citations do not identify exact passage offsets.',
    'R08': 'Existing selected ranges intersect restricted regions; no visual inference or positive restricted proof credit.',
    'R09': 'Historical clipping remains; savings must not expand the clipped body.',
    'R10': 'Question deliberately lacks target PostgreSQL major version; clarification and conditional safeguards required.',
    'R11': 'Several Prusa products delivered together; nearby related context must not transfer procedures across models.',
    'R12': 'Pro Git translations have different source commits; language similarity does not imply synchronized revisions.',
}


@contextmanager
def offline():
    def denied(*args, **kwargs):
        raise RuntimeError('Network and real credentials forbidden in S0/S1 offline preparation')
    with patch.object(socket.socket, 'connect', denied), patch.object(socket, 'create_connection', denied), \
            patch('requests.Session.request', denied), patch('laew.cloud_chat.CloudChatService', denied):
        yield


def seal(root):
    files = [dict(path=p.relative_to(root).as_posix(), sha256=sha(p), bytes=p.stat().st_size)
             for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'integrity.json']
    write(root/'integrity.json', dict(files=files))
    return sha(root/'integrity.json')


def estimate(payload):
    """Historical chars/4 estimate of text, excluding unknown wire tokenizer costs."""
    text = payload['instructions'] + ''.join(m['content'] for m in payload['input'])
    return (len(text)+3)//4


def select_questions(questions):
    """Fixed hazard slots; ascending family order, cyclic DE/EN/PL allocation."""
    if len(questions) != 60 or len({q['id'] for q in questions}) != 60:
        raise ValueError('Expected the 60 exposed development questions')
    allowed = {'id', 'family_id', 'language', 'text', 'split'}
    for q in questions:
        if (set(q) != allowed or q['language'] not in ('de', 'en', 'pl')
                or q['id'] != q['family_id']+'-'+q['language'] or not q['text'].strip()):
            raise ValueError('Only original sanitized questions are accepted')
    lookup = {q['id']: q for q in questions}
    selected = []
    for index, family in enumerate(sorted(FAMILY_SLOTS)):
        language = ('de', 'en', 'pl')[index % 3]
        selected.append(copy.deepcopy(lookup[family+'-'+language]))
    return selected


def verify_pair(record, frame, saved):
    """Replay only rendering, compare all body/range/order identities to saved rows."""
    enc = {}
    for variant in ('S0', 'S1'):
        item = fmt.serialize(frame, variant)
        row = saved[variant]
        if (item.context != row['context'] or frame.contract_sha256 != row['contract_sha256']
                or [list(p) for p in item.body_positions] != row['body_positions']
                or [item.context[a:z] for a,z in item.body_positions] != [p.body for p in frame.passages]
                or row['selected_ids'] != record['selected_ids']
                or row['body_sha256s'] != [p.body_sha256 for p in frame.passages]
                or row['source_ranges'] != [[list(r) for r in p.ranges] for p in frame.passages]):
            raise ValueError('Frozen context/body/order/source/range drift')
        enc[variant] = item
    # S1's serializer removes exactly the two top-level discovery fields.
    # Saved S0 and saved S1 must both match that independently bound contract.
    return enc


def audit_context(record, frame, enc):
    sources = {s.key: s for s in frame.sources}
    risks = {'R01'}
    labels = []
    pg_versions = set()
    prusa = set()
    locators = []
    for index, p in enumerate(frame.passages):
        source = sources[p.source_key]
        meta = json.loads(p.metadata_json)
        visible = {}
        for variant in ('S0', 'S1'):
            item = enc[variant]
            start = 0 if index == 0 else item.body_positions[index-1][1] + len(fmt.SEPARATOR)
            visible[variant] = item.context[start:item.body_positions[index][0]]
        if p.clipped:
            risks.add('R09')
        if source.path not in visible['S1']:
            raise ValueError('Filename lost in model-visible attribution')
        if meta.get('tags') or meta.get('backlinks'):
            risks.add('R06')
        if record['strategy'] == 'structure-v2' and (len(p.ranges)>1 or p.annotations):
            risks.add('R04')
        if p.restricted:
            risks.add('R08')
        match = re.match(r'postgresql-(\d+)-', source.source_id)
        if match:
            pg_versions.add(match[1])
        if source.source_id.startswith('prusa-'):
            prusa.add(source.source_id)
            risks.add('R05')
        if source.source_id.startswith('progit-'):
            risks.add('R12')
        locator = (source.path, meta.get('section_header', ''))
        locators.append(locator)
        labels.append(dict(chunk_id=p.chunk_id, source_key=p.source_key, source_id=source.source_id,
            model_visible_labels=visible, model_visible_filename=source.path,
            model_visible_section=meta.get('section_header'), model_visible_section_path=meta.get('section_path'),
            model_visible_owner=source.scope, model_visible_alias='@knowledge',
            external_only=dict(revision=source.revision, sha256=source.sha256,
                applicability=source.applicability, unicode_ranges=p.ranges, original_mapping_sha256=p.mapping_sha256),
            removed_discovery_fields={k:meta.get(k) for k in ('tags','backlinks')},
            body_sha256=p.body_sha256, body_characters=len(p.body), body_conditions_warnings='preserved verbatim; semantic applicability not inferred',
            passage_boundary='historical separator between fragments; no explicit intra-body gap notice',
            restricted=list(p.restricted), synthetic_or_related=p.annotations, source_range_count=len(p.ranges)))
    if len({s.path for s in frame.sources}) != len(frame.sources):
        risks.add('R02')
    if len(pg_versions)>1:
        risks.add('R03')
    if len(locators) != len(set(locators)):
        risks.add('R07')
    if record['family_id']=='P04':
        risks.add('R10')
    if len(prusa)>1:
        risks.add('R11')
    return dict(question_id=record['question_id'], arm=record['arm'], strategy=record['strategy'],
                variants=['S0','S1'], contract_sha256=frame.contract_sha256,
                risks=sorted(risks), passages=labels, body_characters=sum(len(p.body) for p in frame.passages),
                exact_body_preserved=True, outer_attribution_preserved=True,
                exact_revision_model_visible=False, source_version_hint='filename/heading/body only',
                postgres_major_versions=sorted(pg_versions),
                savings_tokens=enc['S0'].tokens-enc['S1'].tokens)


def make_requests(questions, contexts):
    result = []
    for index, question in enumerate(questions):
        # Alternating arm blocks and format order; each format first in 12/24 pairs.
        arms = ('B','C') if index % 2 == 0 else ('C','B')
        for arm in arms:
            variants = ('S0','S1') if (index + (arm=='C')) % 2 == 0 else ('S1','S0')
            for variant in variants:
                context, contract_hash = contexts[question['id'],arm,variant]
                enclosing = scope_section('global', context)
                payload = serialize(question['text'], enclosing)
                result.append(dict(sequence=len(result)+1, question_id=question['id'], arm=arm,
                    variant=variant, context=enclosing, context_sha256=fmt.digest(enclosing),
                    contract_sha256=contract_hash, payload=payload,
                    payload_sha256=fmt.digest(fmt.canonical(payload))))
    verify_requests(result, questions, contexts)
    return result


def verify_requests(rows, questions, contexts):
    if len(rows) != 48 or [r['sequence'] for r in rows] != list(range(1,49)):
        raise ValueError('Expected the 48 ordered requests')
    qmap = {q['id']:q for q in questions}
    pairs = defaultdict(dict)
    for row in rows:
        if row['variant'] not in ('S0','S1') or row['arm'] not in ('B','C'):
            raise ValueError('Unexpected experimental cell')
        context, contract_hash = contexts[row['question_id'],row['arm'],row['variant']]
        enclosing = scope_section('global', context)
        if (row['context'] != enclosing or row['context_sha256'] != fmt.digest(enclosing)
                or row['contract_sha256'] != contract_hash
                or row['payload'] != serialize(qmap[row['question_id']]['text'], enclosing)
                or row['payload_sha256'] != fmt.digest(fmt.canonical(row['payload']))):
            raise ValueError('Request identity, original question or prompt isolation drift')
        group = pairs[row['question_id'],row['arm']]
        if row['variant'] in group:
            raise ValueError('Duplicate request')
        group[row['variant']] = row
    if set(pairs) != {(q['id'],a) for q in questions for a in ('B','C')}:
        raise ValueError('Unpaired request schedule')
    for group in pairs.values():
        a,b = group['S0'],group['S1']
        if abs(a['sequence']-b['sequence']) != 1:
            raise ValueError('Pairs must execute adjacently')
        pa,pb = copy.deepcopy(a['payload']),copy.deepcopy(b['payload'])
        # Exact source suffix replacement: source contents resembling prompt
        # markers cannot affect the fixed prefix comparison.
        for p,r in ((pa,a),(pb,b)):
            if not p['instructions'].endswith(r['context']):
                raise ValueError('Context is not the exact prompt suffix')
            p['instructions'] = p['instructions'][:-len(r['context'])]
        if pa != pb:
            raise ValueError('S0/S1 differ outside their exact permitted contexts')
    counts = Counter('S0' if g['S0']['sequence']<g['S1']['sequence'] else 'S1' for g in pairs.values())
    if counts != {'S0':12,'S1':12}:
        raise ValueError('Unbalanced format order')


def verify_historical(parent):
    receipts = [verify_manifest(parent,'artifact-integrity.json',PARENT_SHA)]
    freeze = read(parent/'format-freeze.json')
    if sha(fmt.__file__) != freeze['serializer_sha256']:
        raise ValueError('Frozen serializer changed')
    receipts.append(verify_manifest(parent/'inputs','integrity.json',freeze['input_manifest_sha256']))
    config = read(parent/'inputs/study-config.json')
    for entry in read(parent/'inputs/input-integrity.json'):
        if 'root' in entry:
            receipts.append(verify_manifest(Path(entry['root']),entry['manifest'],entry['sha256']))
    corpus = Path(config['corpus'])
    sys.path.insert(0,str(REPO/'tools/corpus'))
    from prepare_real_world_pilot import verify_corpus
    corpus_receipt=verify_corpus(corpus)
    old_corpus=next(e for e in read(parent/'inputs/input-integrity.json') if e.get('verified'))
    if corpus_receipt != old_corpus:
        raise ValueError('Historical frozen corpus receipt changed')
    receipts.append(dict(kind='corpus',**corpus_receipt))
    for root,name,pin in [
        (Path(config['run']).parent,'artifact-integrity.json',config['retrieval_sha']),
        (Path(config['run']),'trace-integrity.json',config['trace_sha']),
        (Path(config['questions']),'input-integrity.json',config['questions_sha']),
        (Path(config['rubric']),'rubric-manifest-v2.1.json',config['rubric_sha']),
        (Path(config['rubric']),'artifact-integrity.json',config['calibration_sha']),
        (PREVIOUS/'laew-luna-live-v1','artifact-integrity.json','29ae7000c7f534127147bf221d54b34b3d0aa9f78c6cc27e0bbae8756d4ec6dc'),
        (PREVIOUS/'laew-scorer-adjudication-v1','artifact-integrity.json','ab55e129aeea66549a1b3e8efecda16f38a08c240f0c3e9bfd7ec6e79326b3d2'),
    ]:
        receipts.append(verify_manifest(root,name,pin))
    for dataset in config['datasets']:
        receipts.append(verify_manifest(Path(dataset['path']),'dataset-integrity.json',dataset['sha256']))
    if sha(REPO/'laew/eval/scoring_calibration.py') != SCORER_SHA:
        raise ValueError('Repaired applicability scorer changed')
    return config,receipts


def preserved(root):
    initial = read(root/'initial-state.json')
    checks = [dict(path=x['path'],unchanged=sha(REPO/x['path']) == x['sha256']) for x in initial['files']]
    checks += [dict(path='.git/index',unchanged=sha(REPO/'.git/index') == initial['index_sha256']),
               dict(path='HEAD',unchanged=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip() == initial['head'])]
    if not all(c['unchanged'] for c in checks):
        raise ValueError('Preexisting repository work changed')
    return checks


def prepare(root, parent=PARENT):
    if root.is_relative_to(REPO) or any((p/'.obsidian').exists() for p in (root,*root.parents)):
        raise ValueError('External non-Obsidian package required')
    if (root/'generator-only').exists():
        raise ValueError('Fresh experiment output required')
    if not (root/'initial-state.json').exists():
        root.mkdir(parents=True,exist_ok=True)
        paths=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=REPO).decode().split('\0')
        write(root/'initial-state.json',dict(
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
            index_sha256=sha(REPO/'.git/index'),files=[dict(path=p,sha256=sha(REPO/p)) for p in paths if p]))
    config,receipts = verify_historical(parent)
    write(root/'historical-verification.json',receipts)
    questions = read(Path(config['questions'])/'questions-only.json')
    selected = select_questions(questions)
    saved_rows = read(parent/'delivery/serialized-contexts.json')
    primary = [r for r in saved_rows if r['kind']=='primary-selected' and r['variant'] in ('S0','S1')]
    if len(primary) != 240:
        raise ValueError('Expected 120 S0/S1 contexts')
    lookup = {(r['question_id'],r['arm'],r['variant']):r for r in primary}
    contexts,audits = {},[]
    for record,frame in load_frames(parent/'inputs'):
        if record['kind'] != 'primary-selected':
            continue
        saved = {v:lookup[record['question_id'],record['arm'],v] for v in ('S0','S1')}
        enc = verify_pair(record,frame,saved)
        audits.append(audit_context(record,frame,enc))
        for variant in ('S0','S1'):
            contexts[record['question_id'],record['arm'],variant] = (enc[variant].context,frame.contract_sha256)
    if len(audits)!=120:
        raise ValueError('Audit incomplete')
    write(root/'provenance-audit.json',audits)
    register = []
    for risk,description in RISK_DEFINITIONS.items():
        affected = [dict(question_id=a['question_id'],arm=a['arm']) for a in audits if risk in a['risks']]
        register.append(dict(id=risk,description=description,affected=affected,
            question_ids=sorted({a['question_id'] for a in affected}),context_count=len(affected),
            status='blocker-if-observed' if risk=='R02' else 'review-required; no semantic approval inferred'))
    write(root/'provenance-risk-register.json',register)
    write(root/'subset.json',dict(selection='Fixed input-hazard slots, ascending family IDs, cyclic DE/EN/PL; no outcome optimization',
        development_only=True, questions=[dict(**q,rationale=FAMILY_SLOTS[q['family_id']]) for q in selected]))
    gen = root/'generator-only'
    gen.mkdir()
    rows = make_requests(selected,contexts)
    write(gen/'questions-only.json',selected)
    write(gen/'requests.json',rows)
    write(gen/'settings.json',dict(provider='chatgpt',model=MODEL,instructions=INSTRUCTIONS,
        language='original question language',history='fresh empty executor per answer',tools=[],store=False,stream=True,
        temperature=None,seed=None,top_p=None,reasoning_effort=None,max_output_tokens=None,
        omitted_settings='Provider defaults retained exactly from the historical payload, not deterministic generation',
        answer_word_target=300,received_output_token_ceiling=4096,received_input_token_ceiling=12000,
        receive_caps_are_not_generation_limits=True,automatic_retries=0,max_attempts=48))
    generator_sha = seal(gen)
    # Only now read scoring material into a disjoint review-only directory.
    review = root/'review-only'
    review.mkdir()
    rubric_root = Path(config['rubric'])
    for name in ('rubric-v2.1.json','source-atoms-v2.1.json','rubric-manifest-v2.1.json'):
        (review/name).write_bytes((rubric_root/name).read_bytes())
    review_sources(review,config)
    review_schema(review,selected,rows,audits,parent)
    totals = {v:sum(estimate(r['payload']) for r in rows if r['variant']==v) for v in ('S0','S1')}
    write(root/'workload.json',dict(attempts=48,questions=12,question_arm_pairs=24,
        per_format_attempts=24,input_text_token_estimate=totals,
        total_input_text_token_estimate=sum(totals.values()),
        paired_input_saving_estimate=totals['S0']-totals['S1'],
        output_planning_range=[48*300,48*900],output_observed_historical_mean_basis='about 511 tokens including reasoning per answer, 36-call pilot',
        output_4096_receive_ceiling_total=48*4096,
        estimator='ceil((instruction characters + original question characters)/4); not a model tokenizer; excludes protocol overhead',
        plan_percentage_estimate=None,live_requests=0,inference_probes=0))
    write(root/'experiment-contract.json',dict(schema='laew-s0-s1-quality-v1',status='offline-prepared-not-authorized',
        parent_manifest_sha256=PARENT_SHA,generator_manifest_sha256=generator_sha,
        repaired_scorer_sha256=SCORER_SHA,provider='chatgpt',model=MODEL,max_attempts=48,
        selected_question_ids=[q['id'] for q in selected],
        source_owner_gate=dict(approved=False,reviewer=None,reason='Visible attribution/version/continuity adequacy remains unapproved'),
        live_authorization=dict(approved=False,attempts=0),
        settings='Frozen exact request payloads; provider defaults omitted as in historical integration',
        model_snapshot_limit='Exact alias required; no separate immutable server snapshot supplied historically',
        exposed_development_data=True,independent_validation=False,
        prohibited=['new retrieval','embeddings','repacking','gold in generation','judge','automatic retries','production changes']))
    write(root/'preparation-verification.json',dict(body_context_pairs_checked=120,payloads=48,
        gold_material_read_after_generator_seal=True,network_calls=0,credential_access=0,
        retrieval_calls=0,embedding_calls=0,source_owner_approval=False,protected=preserved(root)))
    freeze_runtime(root)
    print(json.dumps(dict(root=str(root),payloads=48,audited_contexts=120,input_estimates=totals)))


def freeze_runtime(root):
    paths=['laew/cloud_chat.py','laew/chatgpt_auth.py','laew/rag/pipeline.py',
           'laew/rag/evidence_selection.py','laew/rag/vector_store.py',
           'laew/eval/fixed_body_citations.py','laew/eval/fixed_body_serialization_study.py',
           'laew/eval/real_world_answer_plan.py','laew/eval/real_world_live_pilot.py',
           'laew/eval/serialization_quality_runner.py','laew/eval/serialization_quality_study.py',
           'laew/eval/scoring_calibration.py']
    paths.extend(p.relative_to(REPO).as_posix() for folder in ('agent','llm') for p in (REPO/'laew'/folder).glob('*.py'))
    write(root/'runtime-contract.json',dict(files=[dict(path=p,sha256=sha(REPO/p)) for p in sorted(set(paths))]))


def review_schema(review,selected,rows,audits,parent):
    """No judgment defaults to a pass; blind labels hide the format/arm mapping."""
    qmap = {q['id']:q for q in selected}
    rubric = read(review/'rubric-v2.1.json')['families']
    mapping,cases = [],[]
    pairs = sorted({(r['question_id'],r['arm']) for r in rows})
    for index,(qid,arm) in enumerate(pairs):
        group = {r['variant']:r for r in rows if (r['question_id'],r['arm'])==(qid,arm)}
        # Review orientation uses a different deterministic bit than live order.
        bit = int(hashlib.sha256((qid+'|'+arm+'|review-v1').encode()).hexdigest(),16)%2
        order = ('S0','S1') if bit==0 else ('S1','S0')
        pair_id = f'Pair-{index+1:02d}'
        answers = []
        for position,variant in zip(('X','Y'),order):
            row=group[variant]
            mapping.append(dict(pair_id=pair_id,label=position,question_id=qid,arm=arm,variant=variant,
                                request_sequence=row['sequence'],payload_sha256=row['payload_sha256']))
            answers.append(dict(label=position,answer=None,answer_sha256=None,context=row['context'],
                rubric_family=qmap[qid]['family_id'],reviewer_id=None,origin=None,
                method='manual-semantic',method_id=None,conditions={},conditions_reviewed=False,
                all_substantive_claims_reviewed=False,
                prior_exposure=None,unblinding_exposure=False,
                dimensions={k:None for k in ('technical_correctness','minimum_completeness','delivered_grounding',
                    'citation_accuracy_entailment','warning_prerequisites','product_version_applicability',
                    'unsupported_claims','uncertainty_clarification')},
                annotations=[],condition_decisions=None,citation_groups=[],
                omission_classifications=[],unresolved=[],notes='',adjudication=None))
        cases.append(dict(pair_id=pair_id,question=qmap[qid]['text'],question_id=qid,
            language=qmap[qid]['language'],answers=answers,paired_preference=None,paired_reason=''))
    write(review/'curator-key.json',mapping)
    write(review/'blank-review.json',dict(status='awaiting-future-answers-and-review',independent_validation=False,
        reviewer_id=None,origin=None,prior_exposure=None,all_substantive_claims_reviewed=False,
        cases=cases))
    write(review/'context-evidence.json',[r for r in read(parent/'scoring/per-question.json')
        if r['kind']=='primary-selected' and r['variant']=='S0' and r['question_id'] in qmap])
    render_review(review,read(review/'blank-review.json'),rubric)


def review_sources(review,config):
    corpus=Path(config['corpus'])
    units={u['id']:u for u in read(corpus/'corpus/source-manifest.json')['source_units']}
    texts={sid:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for sid,u in units.items()}
    from laew.eval.scoring_calibration import validate_atoms
    validate_atoms(read(review/'source-atoms-v2.1.json'),texts,units)
    write(review/'source-texts.json',texts)
    write(review/'source-units.json',units)
    (review/'restricted-regions.json').write_bytes((corpus/'review/r3d/restricted-regions.json').read_bytes())


def reviewed_answer_score(root,qid,arm,answer,review):
    """Apply v2.1 only to a complete manual, quote-bound semantic annotation.

    Unregistered optional assertions remain unresolved under the frozen scorer.
    No citation entailment or natural-language meaning is guessed here.
    """
    from laew.eval.scoring_calibration import score_answer,validate_atoms
    from laew.eval.real_world_retrieval import coverage_of
    from laew.eval.retrieval_budget_diagnostics import subtract_regions
    rubric=read(root/'review-only/rubric-v2.1.json')['families']
    family=rubric[qid.split('-')[0]]
    unfixed={key for key,value in family['conditions'].items() if value is None}
    if not isinstance(review.get('condition_decisions'),dict) or set(review['condition_decisions'])!=unfixed:
        raise ValueError('Explicit scoped decisions required for every unfixed condition')
    atoms=read(root/'review-only/source-atoms-v2.1.json')
    texts=read(root/'review-only/source-texts.json')
    units=read(root/'review-only/source-units.json')
    validate_atoms(atoms,texts,units)
    audits=read(root/'provenance-audit.json')
    audit=next(a for a in audits if (a['question_id'],a['arm'])==(qid,arm))
    coverage=coverage_of([dict(source_id=p['source_id'],source_ranges=p['external_only']['unicode_ranges'])
                          for p in audit['passages']])
    coverage=subtract_regions(coverage,read(root/'review-only/restricted-regions.json')['regions'])
    return score_answer(family,atoms,texts,coverage,answer,review)


def bind_answers(root,ledger_path,destination):
    """Offline review rendering from the durable future ledger; preserve failures."""
    import sqlite3
    if destination.exists():
        raise ValueError('Fresh review output required')
    verify(root)
    connection=sqlite3.connect(Path(ledger_path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        records={r['sequence']:r for r in [json.loads(x[0]) for x in connection.execute('SELECT record FROM attempts')]}
        fixture=connection.execute("SELECT value FROM meta WHERE key='fixture'").fetchone()
        rows=read(root/'generator-only/requests.json')
        if not fixture or fixture[0] != fmt.digest(fmt.canonical(rows)):
            raise ValueError('Answer ledger belongs to a different experiment')
    finally:
        connection.close()
    data=read(root/'review-only/blank-review.json')
    key={(m['pair_id'],m['label']):m for m in read(root/'review-only/curator-key.json')}
    rows={r['sequence']:r for r in rows}
    for case in data['cases']:
        for answer in case['answers']:
            mapping=key[case['pair_id'],answer['label']]
            row=rows[mapping['request_sequence']]
            record=records.get(row['sequence'])
            answer['attempt_status']='not-attempted' if record is None else record['status']
            if record:
                if (record.get('request_sha256') != fmt.digest(fmt.canonical(row))
                        or record.get('payload') != row['payload']):
                    raise ValueError('Unbound answer/request identity')
                text=record.get('answer','')
                if record.get('answer_sha256') and record['answer_sha256'] != fmt.digest(text):
                    raise ValueError('Answer text/hash mismatch')
                answer['answer']=text
                answer['answer_sha256']=fmt.digest(text)
    data['status']='future-attempts-bound-awaiting-manual-review'
    destination.mkdir(parents=True)
    write(destination/'blank-review.json',data)
    render_review(destination,data,read(root/'review-only/rubric-v2.1.json')['families'])


def render_review(review,data,rubric):
    # Curator key, format names, telemetry and previous judgments are excluded.
    # Context length can still reveal the treatment; this is label blinding only.
    cards=[]
    for case in data['cases']:
        answers=[]
        for answer in case['answers']:
            rid=case['pair_id']+'-'+answer['label']
            dimensions=''.join(f'<label>{html.escape(k)} <select name="{rid}.{k}"><option value="">Unreviewed</option><option>pass</option><option>partial</option><option>fail</option><option>unresolved</option><option>not-applicable</option></select></label>' for k in answer['dimensions'])
            answers.append(f'<article><h3>Answer {answer["label"]}</h3><p>Status: {html.escape(answer.get("attempt_status","not-attempted"))}</p><pre>{html.escape(answer["answer"] or "No completed answer available; retain this case in failure accounting.")}</pre><details><summary>Exact delivered source context</summary><pre>{html.escape(answer["context"])}</pre></details>{dimensions}<label>Claims, citations, omissions and reasons<textarea name="{rid}.notes"></textarea></label><label>Quote-bound annotations JSON<textarea name="{rid}.annotations"></textarea></label><label>Scoped condition decisions JSON<textarea name="{rid}.condition_decisions"></textarea></label></article>')
        cards.append(f'<section><h2>{case["pair_id"]}</h2><p>{html.escape(case["question"])}</p><details><summary>Frozen rubric criteria — review only</summary><pre>{html.escape(json.dumps(rubric[case["question_id"].split("-")[0]],ensure_ascii=False,indent=2))}</pre></details><div class="answers">'+''.join(answers)+'</div></section>')
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Paired answer manual review</title>
<style>body{font:16px system-ui;margin:24px;max-width:1500px;background:#f4f6f9;color:#172335}section{background:white;padding:20px;margin:20px 0;border:1px solid #ccd4df;border-radius:10px}.answers{display:grid;grid-template-columns:1fr 1fr;gap:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace;max-height:460px;overflow:auto}label{display:block;margin:10px 0}textarea{display:block;width:95%;min-height:100px}select{float:right}button{padding:12px}@media(max-width:850px){.answers{grid-template-columns:1fr}}</style>
<h1>Paired answer manual review</h1><p>Exposed development data. Hidden treatment labels do not establish independent validation. Context length and metadata may reveal the format. No ratings default to approval. Complete the quote-bound JSON claim review as well as this overview.</p>
<label>Reviewer ID<input name="reviewer_id"></label><label>Review origin<select name="origin"><option value="">Unreviewed</option><option>human</option><option>agent</option></select></label><label>Prior exposure and expertise<textarea name="exposure"></textarea></label>
<p>Separate correct-but-ungrounded claims, missing delivered evidence, generation omissions, citation errors, activated safeguards and unresolved applicability. Preserve all negative and failed cases.</p><button id="export">Export local review</button>'''+''.join(cards)+'''
<script>document.querySelector('#export').onclick=()=>{const fields={};document.querySelectorAll('[name]').forEach(e=>fields[e.name]=e.value||null);const blob=new Blob([JSON.stringify({schema:'paired-overview-v1',independent_validation:false,fields},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='manual-overview.json';a.click();URL.revokeObjectURL(a.href);};</script></html>'''
    (review/'manual-review.html').write_text(document,encoding='utf-8')


def verify(root,parent=PARENT):
    if (root/'artifact-integrity.json').exists():
        verify_manifest(root,'artifact-integrity.json',sha(root/'artifact-integrity.json'))
    config,receipts=verify_historical(parent)
    gen=root/'generator-only'
    contract=read(root/'experiment-contract.json')
    verify_manifest(gen,'integrity.json',contract['generator_manifest_sha256'])
    contexts={}
    saved=read(parent/'delivery/serialized-contexts.json')
    for r in saved:
        if r['kind']=='primary-selected' and r['variant'] in ('S0','S1'):
            contexts[r['question_id'],r['arm'],r['variant']]=(r['context'],r['contract_sha256'])
    verify_requests(read(gen/'requests.json'),read(gen/'questions-only.json'),contexts)
    return dict(requests=48,protected=preserved(root),historical_manifests=len(receipts),network_calls=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','verify'))
    parser.add_argument('--artifact-root',required=True,type=Path)
    args=parser.parse_args()
    with offline():
        root=args.artifact_root.resolve()
        if args.mode=='prepare':
            prepare(root)
        else:
            print(json.dumps(verify(root)))


if __name__=='__main__':
    main()
