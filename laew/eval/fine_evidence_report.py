"""Create metadata-only English reports and full offline feasibility ledgers."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import statistics

from laew.eval.complementary_context_study import offline, read, seal, sha, verify_manifest, write
from laew.eval.fine_evidence_study import PARENT, PARENT_SHA

EXTRACTION_REPORT='STAGE_2B2_SOURCE_FAITHFUL_EXTRACTION_FEASIBILITY_20261116.md'
DECOMPOSITION_REPORT='STAGE_2B2_QUERY_DECOMPOSITION_FEASIBILITY_20261116.md'
CONFIGS=('B/K10','B/K20','C/K10','C/K20')
GRANULARITIES=('sentence','paragraph','minimal-span')


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|',
                      *['| '+' | '.join(map(str,row))+' |' for row in rows]])+'\n'


def audit_question(plan):
    """Post-freeze audit, never feedback to the decomposition mechanism."""
    text=plan['question'].casefold()
    findings=['Full original question retained verbatim in every focus embedding; no product/version/negation text removed']
    if plan['status']=='unsplit':
        findings.append('No focused search: enumerations, coordinated operations and implicit dependencies can remain bundled')
    else:
        findings.append('Focus clauses are syntactic emphasis, not verified semantic atoms; full-scope prefix may dilute focus')
    if any(x in text for x in ('if ','unless ','before ','while ','jeśli','przed ','gdy ','wenn ','bevor ','falls ')):
        findings.append('Conditional/prerequisite scope retained in full text; attachment to each focused operation is not semantically verified')
    if any(x in text for x in ('start/stop','files and','checks,','controls and','konfigurac','dateien','plik','firmware')):
        findings.append('Explicit bundled operations/objects may remain within a single focus; dependencies cannot be inferred from syntax')
    if plan['question_id'].startswith('P03'):
        findings.append('Server configuration and retained files are not split into the illustrative four factual dependencies; no WAL-summary/manifest knowledge is injected')
    return findings


def build(package, output):
    if output.exists():
        raise ValueError('Fresh output required')
    verify_manifest(PARENT,'artifact-integrity.json',PARENT_SHA)
    for folder in ('decomposition','inspection','scopes-v3','analysis-v3'):
        verify_manifest(package/folder,'integrity.json',sha(package/folder/'integrity.json'))
    rows=read(package/'analysis-v3/per-question.json')
    strict=read(package/'analysis-v1/per-question.json')
    summary=read(package/'analysis-v3/summary.json')
    plans=read(package/'decomposition/question-only-plans.json')
    workload=read(package/'decomposition/freeze.json')
    by={(r['question_id'],r['configuration']):r for r in rows}
    output.mkdir(parents=True)
    audits=[]; comparisons=[]; ledgers=[]; strata=[]; review=[]
    for plan in plans:
        qid=plan['question_id']
        audit=dict(question_id=qid,language=plan['language'],status=plan['status'],queries=len(plan['queries']),
                   findings=audit_question(plan),origin='agent, question-text-only post-freeze review',
                   independent_semantic_review=False,mechanism_changed=False)
        audits.append(audit)
        for cfg in CONFIGS:
            r=by[qid,cfg]
            known=plan['status']=='unsplit'
            comparisons.append(dict(question_id=qid,configuration=cfg,answerable=r['answerable'],
                status='identical single-query result; exact cached comparison' if known else 'NOT RUN: missing focused embeddings',
                baseline_candidate_minimum_coverage=r['candidate_score']['positive_recall'],
                baseline_candidate_complete=r['candidate_score']['complete'],
                decomposed_candidate_minimum_coverage=r['candidate_score']['positive_recall'] if known else None,
                decomposed_candidate_complete=r['candidate_score']['complete'] if known else None,
                complementary_requirements=[] if known else None,
                equal_raw_slots=int(cfg.split('K')[1]),
                search_allocations=plan['allocations'][cfg.split('K')[1]],
                candidate_duplication=0 if known else None,
                search_count=len(plan['queries']),
                wrong_product_version_status='identical to frozen baseline' if known else 'unmeasured',
                missing_candidate_requirements=r['missing_candidate_requirements'],
                restricted_candidate_exposure=r['candidate_restricted_exposure']))
            for g in GRANULARITIES:
                e=r['extractions'][g]; old=next(x for x in strict if x['question_id']==qid and x['configuration']==cfg)['extractions'][g]
                ledgers.append(dict(question_id=qid,configuration=cfg,granularity=g,answerable=r['answerable'],
                    actual_complete=r['actual_score']['complete'],whole_chunk_complete=r['whole_chunk_oracle']['complete'],
                    extracted_complete=e['complete'] if r['answerable'] else None,
                    gained_vs_actual=e['gained_vs_actual'],lost_vs_actual=e['lost_vs_actual'],
                    critical_retained=e['critical_retained'],critical_missing=e['critical_missing'],
                    conditions_retained=e['conditions_retained'],conditions_missing=e['conditions_missing'],
                    prerequisites_retained=e['prerequisites_retained'],restricted_exposure=e['restricted_exposure'],
                    scope_rejected_packets=len(e['rejected']),
                    strict_v1_complete_pre_correction_unvalidated=old['complete'] if r['answerable'] else None,
                    strict_v1_coverage_pre_correction_unvalidated=old['coverage'] if r['answerable'] else None,
                    main_coverage=e['coverage'] if r['answerable'] else None))
                if e['rejected'] or r['partial_evidence_ambiguities']:
                    review.append(dict(question_id=qid,configuration=cfg,granularity=g,
                        partial_registered_proofs=r['partial_evidence_ambiguities'],
                        boundary_review=e['ambiguities'],rejected=e['rejected'],
                        finding='No absent source range is supplied; rejection is an envelope-library gap, not proof of semantic impossibility'))
    for cfg in CONFIGS:
        for language in ('en','pl','de'):
            group=[r for r in rows if r['configuration']==cfg and r['language']==language and r['answerable']]
            strata.append(dict(configuration=cfg,language=language,answerable=len(group),
                candidate_complete=sum(r['candidate_score']['complete'] for r in group),
                whole_complete=sum(r['whole_chunk_oracle']['complete'] for r in group),
                extraction={g:dict(complete=sum(r['extractions'][g]['complete'] for r in group),
                    coverage=statistics.mean(r['extractions'][g]['coverage'] for r in group)) for g in GRANULARITIES}))
    write(output/'decomposition-audit-all-60.json',audits)
    write(output/'candidate-comparison-all-240.json',comparisons)
    write(output/'complete-gains-regressions-ledger.json',ledgers)
    write(output/'boundary-and-semantic-review-queue.json',review)
    write(output/'language-strata.json',strata)
    combined=[]
    for cfg in CONFIGS:
        group=[r for r in rows if r['configuration']==cfg and r['answerable']]
        split=[r for r in group if next(p for p in plans if p['question_id']==r['question_id'])['status']=='split']
        absent=sum(not r['candidate_score']['complete'] for r in group)
        incomplete=sum(not r['actual_score']['complete'] for r in group)
        split_missing=[r['question_id'] for r in split if not r['candidate_score']['complete']]
        combined.append(dict(configuration=cfg,actual_incomplete=incomplete,candidate_incomplete=absent,
            candidate_missing_share_of_incomplete=absent/incomplete,
            extracted_marginal_complete_ceiling_over_whole=sum(r['proof_body_cost_floor']['complete'] and not r['whole_chunk_oracle']['complete'] for r in group),
            frozen_decomposition_candidate_missing_targets=split_missing,
            additional_decomposition_complete_sets=None,require_both_mechanisms=None,
            candidate_complete_but_whole_over_budget=[r['question_id'] for r in group if r['candidate_score']['complete'] and not r['whole_chunk_oracle']['complete']],
            combined_upper_bound=None,reason='No authorized subquery vectors or candidate rankings; overlap and interaction are unmeasured'))
    write(output/'combined-potential.json',combined)
    # Per-question wide file, including all unavailable/clarification questions.
    import csv
    with (output/'all-60-summary.csv').open('w',encoding='utf-8',newline='') as handle:
        keys=['question_id','language','answerable','decomposition_status','searches']+[cfg+'_'+key for cfg in CONFIGS for key in ('candidate_complete','whole_complete','sentence_complete','paragraph_complete','minimal_span_complete')]
        writer=csv.DictWriter(handle,fieldnames=keys);writer.writeheader()
        for p in plans:
            row=dict(question_id=p['question_id'],language=p['language'],answerable=by[p['question_id'],'B/K10']['answerable'],decomposition_status=p['status'],searches=len(p['queries']))
            for cfg in CONFIGS:
                r=by[p['question_id'],cfg]
                values=[r['candidate_score']['complete'],r['whole_chunk_oracle']['complete']]+[r['extractions'][g]['complete'] for g in GRANULARITIES]
                for key,value in zip(('candidate_complete','whole_complete','sentence_complete','paragraph_complete','minimal_span_complete'),values):
                    row[cfg+'_'+key]=value if r['answerable'] else None
            writer.writerow(row)

    extraction=["""---
title: Stage 2B.2 — Source-faithful evidence extraction feasibility
date: 2026-11-16
status: offline-reference-informed-feasibility-bound-not-a-runtime-extractor
scope: 60 exposed development questions; 48 answerable; no inference
---

# Decision and evidential limits

Prioritize a **bounded question-only decomposition retrieval experiment**, after
the explicitly required embedding authorization. Keep extraction as a supporting
research direction. In the existing pools its incremental complete-case ceiling
over the whole-chunk oracle is only one case in B/K10, B/K20 and C/K20, and zero
in C/K10. Every such extra case is P03-en. That ceiling is registered-proof
availability, not demonstrated coherent 1,000-token feasibility or runtime gain.
No admitted extraction library demonstrates an additional complete case over the
whole-chunk oracle. There is no measured decomposition gain yet.

P03-en's necessary registered text costs **at least 499 estimated body tokens**
before scope and citations. A constructive conservative complete witness costs
**1,335 minimal-span / 1,337 sentence / 1,411 paragraph tokens**. Thus a globally
minimal coherent cost is not proved; these establish a **499–1,335** cost interval
for the most permissive admitted span library. They do not prove that every
defensible extraction exceeds 1,000, nor that 499 tokens form a coherent proof.

# Verification and isolation

Read the requested retrieval/budget, evidence-aware ranking, complementary
selection, v2.1 calibration and scorer-repair/adjudication reports, plus CPU
reranking, FTS5/RRF and hierarchical dense studies. Verified the 777-file frozen
corpus, 201-member historical retrieval package, trace manifest, sanitized
questions, both datasets, rubric and calibration manifests, and the complete
parent budget-study package before source analysis. Reconstructed both chunkers
with `embed=False`; historical context replay matches all 180 contexts byte for
byte, and all 540 v2.1 stage scores reproduce. Source mapping includes visible
related context, normalized Unicode offsets, versions and full hashes.

All 112 registered atoms remain source-bound and exclude ten restricted source
components. The 329 uninspected High findings and inherited source risks stay
open. No original A/B/C, rejected selector, frozen question/source/rubric, index
or saved result changed. No model answer was read or generated. The question-only
decomposition was collected and hash-frozen in a separate `scoring=False`
process before this reference-informed analysis. Rubric labels are used only
in curator extraction/scoring processes, never as decomposition input.

# Three separate extraction libraries

1. **Sentence:** complete source sentences plus explicit local scope closures.
   Fenced listings and tables stay whole. Sentence-boundary detection is a
   conservative Markdown heuristic; semantic minimality remains unresolved.
2. **Paragraph/list unit:** blank-line paragraph/list-item units with the same
   mandatory closures; complete fenced listings and table runs stay whole.
3. **Minimal span:** complete registered spans with mandatory parameter,
   condition, warning, table-header/product-row and procedural-scope closures.
   No paraphrase, unit removal, negation removal or synthetic procedure.

Each result uses one library exclusively. They are not mixed into a best-of
upper bound. Dependencies and rationales are frozen in `scopes-v3/`; they are
agent-authored review assumptions, not a working label-free extraction policy.
Parameters retain definitions/defaults/units and applicable limitations. Restore
dependencies retain checksum cautions and WAL/history/dependency-tracking scope.
Firmware and loading packets retain their prerequisite/completion sequences.
S13 retains both complete version-specific paragraphs and ancestry prohibition.

Every substantive envelope character must be covered by the union of already
eligible, unrestricted candidate source ranges. Missing adjacent text is never
fetched or credited. An envelope touching a restricted component is rejected.
Source identity and full revision establish document scope; substantive parameter
definitions remain body evidence. Each source is cited with its full normalized
SHA-256 and revision; every fragment carries exact Unicode offsets. Source order
and explicit `[separate source passage]` separators prevent presenting disjoint
passages as consecutive steps. No spans from different versions are substituted.
The immutable source manifest resolves citations to original locations, URLs,
page/line maps and document applicability. This is a proposed diagnostic renderer,
not the original production renderer or a metadata-only selector revival.

A disclosed **strict-v1** sensitivity also required every section-heading body
inside candidate ranges, although ordinary source/section metadata already
supplies that scope. This overconstraint created artificial heading-availability
gaps. Its rules and all outputs are preserved. The main scope rule removes only
that requirement; substantive closures are unchanged. This revision occurred
after observing strict-v1 and is not blind validation.

A subsequent scope-retention acceptance test found an oracle bug: one packet
could incidentally cover another registered proof without that proof's declared
neighboring scope. The corrected v3 optimizer rejects every such union. Scope
rules and decomposition were not tuned. All pre-correction v1/v2 outputs remain
preserved and explicitly unvalidated as coherent witnesses; `analysis-v3/` is
authoritative. This mechanical correction leaves aggregate completeness/cost
findings unchanged but is necessary for the witness safety claim.

# Complete-context and coverage measurements

Counts use 48 answerable variants from 16 dependent families. The other 12
variants remain in exposure, cost and ambiguity ledgers with N/A positive recall.
"""]
    extraction.append(table(['Configuration','Actual','Whole-chunk oracle','Sentence witness','Paragraph witness','Minimal-span witness','Proof-only complete upper bound'],[
        [cfg,summary[cfg]['actual_complete'],summary[cfg]['whole_complete'],
         *[summary[cfg]['extraction'][g]['complete'] for g in GRANULARITIES],summary[cfg]['necessary_body_floor_complete_upper']] for cfg in CONFIGS]))
    extraction.append(table(['Configuration','Candidate coverage','Sentence coverage','Paragraph coverage','Minimal-span coverage'],[
        [cfg,f"{statistics.mean(r['candidate_score']['positive_recall'] for r in rows if r['configuration']==cfg and r['answerable'])*100:.2f}%",
         *[f"{summary[cfg]['extraction'][g]['coverage']*100:.2f}%" for g in GRANULARITIES]] for cfg in CONFIGS]))
    extraction.append("""
These extraction counts are **constructive lower bounds within conservative
envelope libraries**, not replacement-selector results and not global optima.
They can be lower than the whole-chunk rubric oracle because the added source
coherence closures are stricter than the frozen registered minimum. This does
not overturn historical rubric completeness. It exposes a boundary judgment to
review. No fallback to another library or baseline witness inflates these counts.

The proof-only upper bound allows zero citation overhead and no neighboring
context. Every reference-complete extraction must contain one whole registered
proof for every active requirement; unioning those atoms gives a necessary body
cost. This is deliberately optimistic and never called safe evidence. Missing
registered proof does not prove that all unregistered equivalent text is absent.
All such equivalence and partial-span disputes remain open.

The optimizer exhausts all unions of admitted proof packets, keeping source
interval geometry rather than pruning by proof masks: grouped citations make
costs nonadditive. The finite-library optimum is exact, including above-budget
minimum-complete witnesses. This does **not** prove a global semantic optimum
over arbitrary excerpts. No heuristic state cap or statistical claim is used.

# Whole chunks, source attribution control and focus cases

The serialization control rerenders the **same original minimum-complete whole
chunk witness** using grouped source ranges/citations; it is not newly optimized.
It removes synthetic chunk context/navigation and same-source overlap. It is
not an attribution-only control. Therefore
token reductions must not all be attributed to finer evidence boundaries.
""")
    focus=[]
    for qid,cfg in [('P03-en','B/K10'),('P03-en','C/K20'),('S06-en','B/K10'),('S12-en','B/K10'),('S13-en','B/K10'),('S13-en','C/K10')]:
        r=by[qid,cfg];control=r['same_whole_witness_grouped_citation_control']
        focus.append([qid,cfg,r['whole_chunk_oracle']['min_complete_tokens'],control['tokens'] if control else 'N/A',r['proof_body_cost_floor']['min_complete_tokens'],*[r['extractions'][g]['min_complete_tokens'] or 'scope gap' for g in GRANULARITIES]])
    extraction.append(table(['Question','Pool','Original whole','Same witness grouped citation control','Necessary body floor','Sentence complete','Paragraph complete','Minimal-span complete'],focus))
    extraction.append("""
**P03-en:** B/K10 and K20 have all six requirements; C gets the missing retention
proof only at K20. All three complete pools have the same source-level extraction
costs. At 1,000 tokens the conservative libraries retain 4/6 requirements, versus
2/6 for B's whole-chunk oracle and 1/6 in C/K20. These are partial coverage gains,
not complete answers. P03-pl remains missing all registered minimum proof;
P03-de has mixed retrieval and budget/scope gaps. An exhaustive search within
this library cannot settle whether a less conservative, domain-approved boundary
could fit all six requirements.

**S12:** B/en and B/de already have whole-chunk rubric-complete witnesses at
889 tokens (827 at K20). The stricter migration packets also require source
prerequisite/start/stop invocation scope, including same-session and primary/
standby switch conditions. Those complete closures are absent from these pools,
so no extraction witness is claimed. The API/session/byte-exact metadata atoms
alone cost 137 tokens, but are not a complete operational migration procedure.
This is an unresolved scope-closure issue, not a newly absent registered fact or
proof that a safe compact explanation is impossible. C lacks the registered
target-17 procedure; compacting old-version text cannot repair it.

**S13:** both complete source paragraphs preserve 11/17 defaults, explicit
current/target timeline behavior and the pre-base-backup branch prohibition.
They fit in 345–346 tokens with full source hashes/revisions. Their whole-chunk
witnesses already fit at 724 B / 818 C tokens: this is a cost reduction, not an
additional feasible complete case. B/pl still needs K20 to obtain the proof.

**P02:** no pool supplies the complete sheet/bed proof. B/K20-pl and C/K20-pl
contain 2/3 minimum requirements; other variants have less. Need-based cleaning,
same-sheet first-layer scope, IPA qualifiers, water fallback and burn conditions
remain separate. Adjacent diagrams and unadjudicated semantic extensions earn
no credit. Compression never repairs an absent registered requirement.

**S06:** the B/en complete source packet fits in 461–521 tokens, preserving
model/selftest/media/rollback scope and complete selected update steps. This was
already a 755-token feasible whole-chunk case. All language/configuration
prerequisite losses/gains remain in the full ledger.

**S07/S11:** complete tube-maintenance or MK4S-side evidence remains missing.
Expanded XL loading retains heat-before-feed and purge-completion scope; MMU3
packets retain correct firmware identity, power, single-device USB and completion.
Some of those source closures are outside candidate ranges and are rejected.
No generic product neighbor or compressed MMU procedure fills the missing side.

# Safety, ambiguity and bounds audit

`complete-gains-regressions-ledger.json` includes every gain, loss and tie for
all 60 questions × four pools × three libraries, including optional/conditional
branches. Critical/condition denominators are fixed source requirements, not
observed advice or safe-answer counts. A minimum method can omit an unadvised
branch, but any supplied source packet retains its mandated local safeguards.
No semantic warning detector, independent bilingual adjudication or automated
answer correctness evaluation is claimed. Source identity validates which
snapshot supplied text; it does not certify every unrelated assertion in it.

Every admitted best-budget and minimum-complete witness is exact source text.
Restricted-region exposure is zero in extraction witnesses in all libraries.
Candidate restrictions remain unchanged and are recorded separately; rejected
packets never clear a restriction. S14 torque, S15 target context and S16 visual
facts remain unavailable; P04 still requires actual server major version.
All 12 N/A variants remain unresolved on positive technical retrieval metrics.
""")
    audit_rows=[]
    for cfg in CONFIGS:
        allrows=[r for r in rows if r['configuration']==cfg]
        for g in GRANULARITIES:
            es=[r['extractions'][g] for r in allrows]
            audit_rows.append([cfg,g,sum(len(e['critical_retained']) for e in es),sum(len(e['conditions_retained']) for e in es),
                f"{statistics.mean(e['witness']['rendering']['fragments'] for e in es):.2f}",
                f"{statistics.mean(e['witness']['rendering']['attribution_and_separator_chars'] for e in es):.1f}",
                sum(bool(e['rejected']) for e in es),summary[cfg]['extraction'][g]['cannot_fit_admitted_complete']])
    extraction.append(table(['Pool','Library','Critical /132','Conditions /147','Mean fragments /60','Mean citation+gap chars /60','Rows with rejected closure','Complete admitted set >1000 /48'],audit_rows))
    extraction.append("""
Critical and condition omissions in an oracle-selected subset remain visible;
the aggregate objective maximizes minimum-method coverage and does not certify
every possible optional branch. A whole-chunk rubric-complete case rejected by
these closures needs domain review rather than relabeling the old result.

# Combined potential and architectural decision
""")
    extraction.append(table(['Pool','Actual incomplete','Candidate incomplete','Share of incomplete with missing candidate proof','Max extraction-only complete gain over whole'],[
        [r['configuration'],r['actual_incomplete'],r['candidate_incomplete'],f"{100*r['candidate_missing_share_of_incomplete']:.2f}%",r['extracted_marginal_complete_ceiling_over_whole']] for r in combined]))
    extraction.append("""
The partition is reference-relative; missing candidates can coexist with budget
or selection losses. Increasing K10→K20 gives B four and C three additional
candidate-complete cases, but unchanged selection delivers **zero** new complete
contexts. This establishes headroom for retrieval discovery, not decomposition
effectiveness. Decomposition's additional sets, the overlap with extraction and
cases requiring both mechanisms are **unmeasured** until approved embeddings
and rankings exist. No combined numerical bound is fabricated or formed by
adding overlapping improvements. P03-en/C-K10 illustrates a hypothetical need
for both retention discovery and cheaper coherent context, but neither missing
retention discovery by this decomposer nor full 1,000-token extraction is proved.

| Direction | Bottleneck and evidence | Complexity / overhead / risk |
|---|---|---|
| Question decomposition — primary next experiment | Missing complementary candidates; 27/48 pools incomplete at K10; actual gain pending | Small rule module, 41 new query vectors, 101 vs 60 searches per chunker; implicit-dependency and multilingual split errors |
| Source-faithful extraction | Smaller bodies and attribution; S13 345–346 tokens, S06 461–521; no new complete case over whole oracle | High semantic-boundary risk; scope closures can be unavailable; label-free runtime performance unknown |
| Decomposition + extraction | Both missing proof and oversized context | Conditional architecture hypothesis; no measured joint gain and no deployment justification |
| Semantic reranking | Relevance/order among available candidates | Previous CPU BGE adds 27.74 s median at K20; GTE 12.44 s, regressions remain; no repair of absent evidence |
| Hierarchical/section-aware | Multi-section discovery | Earlier fixed document routing lost valid candidates, stress benefit depended on layout, authored long-document set showed no gain |
| Larger context | Proven oversized witnesses | P03 conservative witnesses fit above 1,000; larger budget cannot supply absent proof; larger generation context is unmeasured |
| Existing B/C | Reproducible baselines | Keep unchanged; production A unchanged |

Rejected FTS5/equal-weight RRF and lexical/redundancy selectors remain rejected;
none is revived under a new name. More complexity has no presumption of benefit.
The sole proposed next experiment is the frozen conservative decomposition at
equal total raw candidate budgets, with full regressions/safety/version review.
If it shows no convincing gain, retain B/C without further architecture work.
Extraction should progress only with explicit domain agreement on boundaries.
No new holdout now. Approximately 24 genuinely new intent families belong only
after a promising mechanism is implemented and frozen. All present variants are
exposed development data, without significance/generalization/answer-quality claims.

# Artifacts and reproduction
""")
    extraction.append(f"External package: `{package}`.\n\n")
    extraction.append("""
- `analysis-v3/per-question.json` and CSV: all 240 pool/question rows, whole
  costs, body-cost floors, three separate libraries, best-budget and unbounded
  complete witnesses, full attribution, offsets, supports and rejected closures.
- `analysis-v1/`, `analysis-v2/`, `scopes/`, `scopes-v2/`: preserved
  pre-correction runs; coherent-witness claims there are unvalidated.
- `reports-final/`: all-60 wide CSV, complete gains/regressions/ties, safety/condition
  and language ledgers, source-bound boundary review queue and combined limits.
- `decomposition/`: question-only freeze, all 60 plans and exact 41 pending inputs.
- `inspection/`, `scopes-v3/`, snapshots, logs and integrity manifests:
  source/proof provenance and validation. All semantic review origins are agent.

Use `.venv/Scripts/python.exe -B scripts/run_isolated.py --keep-diagnostics eval
laew.eval.fine_evidence_study` with modes `prepare`, `inspect`, `scopes`, `analyze`;
pass `--config <package>/study-config.json` and a fresh relative `--output`.
Analysis additionally takes `--scopes <package>/scopes-v3` and `--decomposition
<package>/decomposition`. Copy retained outputs from the runner's `work` directory
to a fresh external directory in the same shell call. The report module accepts
`--package` and a fresh relative `--output`. It never contacts an embedding service.
Validation: **67 tests passed, zero skipped**, through `scripts/run_isolated.py`,
covering the new oracle/decomposition contracts, all frozen witness source ranges,
mandatory-scope retention, source/version/restriction behavior, exact prior budget
oracles and v2.1 calibration. Initial development failures and the transient
sandbox standard-library read failure are preserved in logs; the final complete
run passes. `git diff --check` passes. Final file inventory, checksums and Git
status are in the package's final validation receipt. Repository changes comprise
four evaluation-only modules, one test module, these two reports and two additive
documentation-index entries. No production file changed; the initial working
tree was clean. No Git add, commit, push, reset or clean was executed.
""")
    (output/EXTRACTION_REPORT).write_text('\n\n'.join(extraction),encoding='utf-8')

    decomposition_text=["""---
title: Stage 2B.2 — Query decomposition design and embedding authorization gate
date: 2026-11-16
status: question-only-design-frozen-retrieval-comparison-partial-awaiting-authorization
scope: 60 exposed development questions; no new inference
---

# Status

The deterministic question-only mechanism is frozen; **41 unique focused inputs
are missing from the verified cache**. No new embedding, service request,
tokenizer request, download, restart or reconfiguration occurred. Finish the
offline study and **STOP for explicit user authorization** before computing them.
There is no measured decomposition retrieval gain or joint architecture result.

# Frozen mechanism and input isolation

`laew/eval/question_decomposition.py` imports only `re` and future annotations.
It consumes the original question string only, never question IDs, requirement
labels, reference answers/proofs, oracle outputs, previous failures, source text,
Luna answers or a model service. Its freeze precedes reference-based source
analysis. `prepare` uses `load_inputs(scoring=False)`. AST isolation and synthetic
EN/PL/DE scope/budget/dedup tests are included.

Version `explicit-question-focus-v1` detects interrogative clauses following
question marks, semicolons/newlines, conjunctions before interrogatives and
commas before interrogatives. It groups excess requests contiguously to at most
four foci. An unsplittable question retains its single original query. Otherwise
the search plan retains the original query plus one query per focus:

`<entire original question>\\nRequested part: <verbatim-derived request clause>`

No product/version/negation or condition is removed. This deliberately conservative
prefix keeps question scope but can dilute the focused embedding. No hidden
technical dependency or expected answer is added. Interrogative splitting is
surface syntax, not verified semantic understanding. No rule refinement or
question-specific runtime decomposition was made after inspection of these
plans or reference scoring. P03's illustrative factual decomposition was not
hardcoded: its server/retained-file/default-retention questions can remain bundled.
"""]
    decomposition_text.append(table(['Language','Questions','Split','Searches per chunker'],[[l,workload['languages'][l]['questions'],workload['languages'][l]['split'],workload['languages'][l]['searches']] for l in ('en','pl','de')]))
    decomposition_text.append("""
Exactly 20 questions split; 40 remain original-only. EN/DE each split six questions,
PL eight: this asymmetry is a design limitation, not cross-language equivalence.
The post-freeze 60-row audit records all unsplit and conditional-scope limitations.
Examples: S06/en's model/media/entry enumeration and S10/en's coordinated
populate/publish operations do not split. EN auxiliary interrogatives such as
`does`, `should` or `can` are outside this narrow detector; P04/S02/S15 can remain
unsplit despite explicit multiple requests. P02/en's implicit sheet/bed/first-layer
dependencies are not inferred. P03's configured server scope remains intact,
but the rule cannot invent the necessary WAL-summary dependency identifiers.
S07/S11 focus explicit operation versus maintenance/connection questions, while
full question scope remains attached to every search. Conditions can still be
semantically associated with the wrong focused operation; preserving the text
does not prove that the embedding or downstream model interprets it correctly.

# Fair comparison fixed before retrieval

Use the existing model, 1,024 dimensions, native cosine index and >=0.3 threshold,
unchanged source restrictions, chunking and source/version identities. For each
question divide **10 or 20 total raw result slots across all queries**, assigning
the remainder to earlier queries. Search the original first. Merge round robin
in query order, preserving each native ranking; remove exact duplicate chunk IDs
only and apply the unchanged threshold. No source/body/language dedup, RRF, query
score boosts or backfill. Duplicate/threshold losses reduce the unique pool
rather than silently spending more retrieval budget. Preserve original cosine,
query origin/rank and source metadata. Allocation and merge code are testable
without new vectors, but no focused ranking has been computed.

This enforces equal **raw search-result** budgets as well as a maximum equal
unique-candidate budget. Focused searches may return fewer unique candidates
because of duplicates; that cost belongs in the result. Compare original single
B/C K10, original single K20 and decomposed 10/20 separately. An optional increased
budget of 20 per query is a separate cost/coverage condition, never attributed
to decomposition alone. Do not compare its larger pool to original K10 as a
pure decomposition effect.

Across both chunkers, each fair K condition needs 202 native searches instead of
120; both fair budgets together need 404 searches and 3,600 raw result slots.
The optional 20-per-query condition uses 4,040 raw slots versus 2,400 original K20
slots (+68.33%). Query vectors are shared across chunkers and budgets. HNSW CPU
time, duplication, discovered requirements, safety/version errors and latency
remain unmeasured for the 20 changed questions. Forty original-only questions
have exactly the original rankings/scores at either K; these identical rows are
recorded, not presented as a successful multi-query retrieval experiment.
""")
    decomp_rows=[]
    for cfg in CONFIGS:
        relevant=[r for r in comparisons if r['configuration']==cfg]
        known=[r for r in relevant if r['status'].startswith('identical') and r['answerable']]
        future=next(x for x in combined if x['configuration']==cfg)
        decomp_rows.append([cfg,len(known),sum(r['baseline_candidate_complete'] for r in known),len(future['frozen_decomposition_candidate_missing_targets']),', '.join(future['frozen_decomposition_candidate_missing_targets'])])
    decomposition_text.append(table(['Pool','Answerable original-only rows','Their candidate-complete count','Candidate-incomplete split targets','Split targets requiring discovery'],decomp_rows))
    decomposition_text.append("""
This last column bounds how many currently candidate-incomplete rows the frozen
mechanism can possibly repair at that K; it is not a predicted gain. It cannot
help any unsplit row beyond its unchanged original candidate pool. Equal-budget
allocation may also lose original complementary candidates, and all regressions
must be scored after authorization. No aggregate unknown metric is imputed zero.

# Exact proposed embedding workload — authorization required
""")
    decomposition_text.append(table(['Item','Value'],[
        ['New unique embedding inputs',workload['new_unique_inputs']],['Verified existing query hits',workload['verified_unique_cache_hits']],
        ['Estimated input tokens, ceil(chars/4) per input',workload['estimated_tokens_chars4']],['UTF-8 input bytes',workload['utf8_bytes']],
        ['Total query strings/searches per chunker',workload['queries']],['Output dimensions',1024],['New float32 output bytes',41*1024*4],
        ['Model','laew-qwen3-embedding / Qwen3-Embedding-0.6B / Q8_0'],['Frozen model catalog identity SHA-256',workload['model_identity_sha256']],
        ['Expected GGUF weight SHA-256','06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439']]))
    decomposition_text.append("""
The token figure is an estimate, not a model-tokenizer measurement. There is no
corpus re-embedding and no padding/probe/answer input. The complete exact text
list with per-input hashes and question ownership is
`decomposition/pending-embedding-inputs.json`. No inference code is invoked by
this package. Original SQLite is opened read-only and immutable; missing keys
fail closed. New approved vectors must go to a separate append-only study cache,
leaving the frozen corpus and 60 original query embeddings untouched. Before any
future request, verify the approved weight/model/pooling/dimension identity and
the exact workload manifest; catalog drift must not silently rekey old vectors.

Historical 60 query inputs took 28.28 seconds in eight batch requests. Scaling
41 inputs alone gives 19.3 seconds, but focused strings are longer and hardware
load differs. Plan **roughly 20–60 seconds warm embedding computation**, excluding
model load and verification; this is a planning range, not measured runtime or
a promised GPU speed. A six-request plan with at most eight inputs per request
requires only these 41 new vectors. Start sequentially; multiple server slots
help only with approved concurrent requests or actual server batching, and the
throughput gain is unmeasured.

Read-only local inspection found an RTX 4060 with 8,188 MiB total and only
455 MiB free at inspection time, plus 16 available logical CPU threads. Free
memory is transient. The ~633 MB model weights alone exceed that observed free
VRAM. The user should prepare GPU capacity; do not stop another process. Budget
approximately 2–4 GiB free VRAM for weights/context/workspace as a conservative
planning allowance; actual allocation has not been measured. CPU-only execution
is possible but slower; reserve several GiB RAM and 8–16 threads as appropriate.
GPU offload should help this batched embedding workload if capacity is available.

Proposed llama.cpp settings, **for the user to prepare**, not executed here:

```text
--alias laew-qwen3-embedding --embedding --pooling last
--embd-normalize 2 --n-gpu-layers all
--ctx-size 8192 --batch-size 2048 --ubatch-size 512
--parallel 4 --threads 8 --threads-batch 8
--host 127.0.0.1 --port 8081
```

Use the exact authorized existing GGUF, 1,024 native dimensions and historical
query formatting; no newly introduced instruction prefix beyond the frozen
focus syntax. These flags were checked against the local binary's `--help`
(build 11540, commit `1e6f04a75`); it was not started as a server. Last-token
pooling and the model's 1,024-dimensional configuration are also documented by
the [official Qwen GGUF model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/blob/a872aacee2f036e1a5586cc8e558405c8f1c400f/README.md).
Normalization and pooling must preserve the historical embedding semantics;
the historical catalog does not by itself prove all launch flags. Exact GGUF
pooling metadata/current approved service settings still need verification
before inference. No dimensionality truncation, different provider or different
model may bypass this gate. Four slots are a proposed capacity option; one
sequential client does not automatically benefit from them.

This service has **not** been accessed, started, restarted, downloaded or changed.
The requested gate is the reason the full candidate comparison and combined
decomposition/extraction analysis remain incomplete. Explicit user authorization
and preparation of the correct server are required to continue the 41-input job.

# Next experiment and stop

The primary next experiment is **this frozen question-only decomposition** at
equal total raw budgets, with separate increased-budget diagnostics if requested.
Measure minimum candidate coverage/completeness, newly discovered requirements,
all lost prerequisites/conditions, product/version scope, cross-language behavior,
exact ID duplication, query/search count and timings. Reuse the frozen source
extraction libraries only in a separate scorer/oracle process; do not add their
individual gains when cases overlap. Retrieval completeness still does not
establish answer correctness. Preserve the 40 identical comparisons and all
20 changed rows including zero/negative results.

No production RAG or A/B/C changes, LLM-based decomposition, Luna inference,
LLM judge, generated model answer, new source/rubric, new model/corpus rebuild
or independent holdout is authorized by this report. The ~24-family future
holdout remains uncreated. No Git staging, commit, push, reset or clean occurred.
""")
    decomposition_text.append(f'External reproducible package: `{package}`. The extraction report records verification, ledgers, bounds, architecture comparison and reproduction.\n')
    (output/DECOMPOSITION_REPORT).write_text('\n\n'.join(decomposition_text),encoding='utf-8')
    names=[p.name for p in output.iterdir() if p.is_file()]
    seal(output,names,reporter_sha256=sha(__file__))
    print(dict(output=str(output),files=len(names),question_rows=60,comparison_rows=240,ledger_rows=len(ledgers)))


def build_complete(package, output):
    """Final report after the separately authorized 41-input embedding job."""
    if output.exists():
        raise ValueError('Fresh output required')
    for folder in ('embeddings-authorized','decomposition-retrieval','decomposition-scores','analysis-v3','reports-final'):
        verify_manifest(package/folder,'integrity.json',sha(package/folder/'integrity.json'))
    rows=read(package/'decomposition-scores/per-question.json')
    baseline=read(package/'analysis-v3/summary.json')
    summary=read(package/'decomposition-scores/summary.json')
    job=read(package/'embeddings-authorized/metadata.json')
    dispatch=read(package/'embeddings-authorized/dispatch-ledger.json')
    retrieval=read(package/'decomposition-retrieval/provenance.json')
    plans=read(package/'decomposition/question-only-plans.json')
    output.mkdir(parents=True)
    paired=[];strata=[];combined=[]
    for r in rows:
        paired.append({k:r[k] for k in ('question_id','family_id','language','arm','condition','answerable',
            'baseline_configuration','candidate_score','baseline_candidate_score','gained_requirements','lost_requirements',
            'critical_gained','critical_lost','condition_gained','condition_lost','missing_critical','missing_conditions',
            'raw_budget','unique_eligible','duplicate_slots','searches','restricted_candidate','baseline_restricted',
            'new_restricted_regions','unregistered_scope_neighbors')})
    for arm in ('B','C'):
        for condition in ('equal10','equal20','expanded20perquery'):
            group=[r for r in rows if r['arm']==arm and r['condition']==condition and r['answerable']]
            s=summary[arm+'/'+condition]
            combined.append(dict(arm=arm,condition=condition,candidate_complete=s['candidate_complete'],
                newly_candidate_complete=s['gained_complete'],lost_candidate_complete=s['lost_complete'],
                reference_candidate_availability_upper=s['candidate_complete'],
                complete_coherent_extraction_lower={g:s['extraction'][g]['complete'] for g in GRANULARITIES},
                newly_available_complete_extraction={g:s['extraction'][g]['gained_complete'] for g in GRANULARITIES},
                cases_demonstrably_requiring_both={g:[r['question_id'] for r in group if r['extractions'][g]['complete']
                    and not r['baseline_extraction'][g]['complete'] and r['whole_chunk_oracle'] is not None and not r['whole_chunk_oracle']['complete']] for g in GRANULARITIES},
                caveat='Availability upper is registered-proof-relative and ignores source closure/citation cost; libraries are separate, never pooled'))
            for language in ('en','pl','de'):
                part=[r for r in group if r['language']==language]
                strata.append(dict(arm=arm,condition=condition,language=language,answerable=len(part),
                    before_coverage=statistics.mean(r['baseline_candidate_score']['positive_recall'] for r in part),
                    after_coverage=statistics.mean(r['candidate_score']['positive_recall'] for r in part),
                    before_complete=sum(r['baseline_candidate_score']['complete'] for r in part),
                    after_complete=sum(r['candidate_score']['complete'] for r in part)))
    write(output/'complete-paired-ledger.json',paired)
    write(output/'combined-potential.json',combined)
    write(output/'language-strata.json',strata)
    # One explicit row per exposed variant, including N/A families.
    import csv
    with (output/'all-60-final.csv').open('w',encoding='utf-8',newline='') as handle:
        keys=['question_id','language','answerable','searches']+[arm+'/'+cond+'/'+metric for arm in ('B','C') for cond in ('equal10','equal20','expanded20perquery') for metric in ('candidate_complete','candidate_coverage','coherent_span_complete')]
        writer=csv.DictWriter(handle,fieldnames=keys);writer.writeheader()
        lookup={(r['question_id'],r['arm'],r['condition']):r for r in rows}
        for p in plans:
            row=dict(question_id=p['question_id'],language=p['language'],answerable=lookup[p['question_id'],'B','equal10']['answerable'],searches=len(p['queries']))
            for arm in ('B','C'):
                for cond in ('equal10','equal20','expanded20perquery'):
                    r=lookup[p['question_id'],arm,cond];prefix=arm+'/'+cond+'/'
                    row[prefix+'candidate_complete']=r['candidate_score']['complete']
                    row[prefix+'candidate_coverage']=r['candidate_score']['positive_recall']
                    row[prefix+'coherent_span_complete']=r['extractions']['minimal-span']['complete'] if r['answerable'] else None
            writer.writerow(row)
    preface="""---
title: Stage 2B.2 — Query decomposition and combined feasibility results
date: 2026-11-16
status: completed-authorized-development-study-reject-current-decomposition
scope: all 60 exposed questions; 41 authorized new query embeddings; production unchanged
---

# Decision

**No change to A/B/C. Reject this conservative question-focus decomposition.**
It discovers zero new candidate-complete cases at equal total raw budgets, loses
complete cases and technical prerequisites, and yields zero newly complete
coherent extracted sets. A larger 20-per-query pool has small partial coverage
gains but no additional complete case, plus one new restricted B region.
These results do not reject query decomposition in principle. They reject the
tested frozen syntax/focus mechanism, merge and raw-budget allocation on these
exposed development questions. No post-result rule tuning was performed.

Source-faithful extraction has measurable cost potential but no demonstrated
complete-case gain beyond existing whole-chunk feasibility. Its incremental
reference ceiling is at most one P03-en case per B/K10, B/K20 and C/K20 pool;
that case has no demonstrated coherent 1,000-token witness. A combination has
**zero measured new complete contexts** in every separately evaluated extraction
library. No numerical gains are added across overlapping cases or libraries.

The one primary next-step recommendation is **no new architecture engineering
experiment yet**. Resolve the source-boundary/domain judgments first, especially
P03/S12/S04. This is the permitted no-change outcome. Repeated lexical selectors,
this decomposer, FTS5/RRF or a costly CPU reranker do not have supporting evidence
for another implementation/tuning round. If research continues, narrower evidence
boundaries need independent domain agreement before a label-free extractor is
engineered; the current oracle is not one.

# Authorization, embedding identity and measured cost

The initial cache inspection found exactly 41 missing unique focused inputs.
Offline source extraction, workload counts and the question-only freeze were
finished first. The user then explicitly authorized generation and continuation.
All 41 texts were submitted exactly once in six requests, without probes, corpus
re-embedding, model answers or an LLM judge. The job used the user-prepared local
service; no service was started, restarted, downloaded or reconfigured.
"""
    parts=[preface]
    tokens=sum(r['usage']['prompt_tokens'] for r in dispatch)
    parts.append(table(['Measurement','Value'],[
        ['Model','laew-qwen3-embedding; Qwen3-Embedding-0.6B Q8_0; 1,024 dimensions'],
        ['Verified exact GGUF SHA-256','06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439'],
        ['New inputs / requests',f"{job['inputs']} / {job['requests']}"],
        ['Estimated chars/4 / actual server prompt tokens',f'3189 / {tokens}'],
        ['Measured warm job time',f"{job['seconds']:.3f} seconds"],
        ['Observed server settings','pooling last; 2 slots; ctx 16384; batch 1024; ubatch 1024'],
        ['Original native control rows','240/240 exactly equal'],
        ['Logical searches / physical calls including repeat audits',f"{retrieval['logical_searches']} / {retrieval['physical_searches']}"],
        ['Distinct first-search time sum',f"{retrieval['native_search_first_seconds']:.3f} seconds; excludes model/loading/source checks/repeats"],
    ]))
    parts.append("""
The current model catalog differs only in its server-supplied `created` timestamp.
Exact weight SHA, alias, Q8_0 metadata, last-token pooling and 1,024 dimensions
were separately verified. This drift is explicit in `embeddings-authorized/`;
the historical SQLite was not rekeyed or modified. New vectors use a separate
catalog-bound cache. This is not a model substitution. The user-prepared settings
differ from the earlier suggested slot/context values; inference semantics and
model identity were preserved. Local sandbox loopback access required tool-level
escalation; the user's authorization covered this job. No rejected approval or
pending computation remains. No further embedding computation is required.

# Frozen deterministic design and fair comparisons

`explicit-question-focus-v1` consumes only the original question string and
imports only `re`. It has no reference, source, answer or failure inputs. It splits
explicit interrogative clauses at question/semicolon/newline boundaries and
conjunctions/commas before interrogatives, groups contiguous excess clauses to
at most four foci, and retains the original search. Each focused embedding is
the full original question plus `Requested part: <request clause>`. This retains
products, versions, conditions and negations, but is a syntactic emphasis
mechanism rather than verified atomic semantic decomposition. No LLM service,
question-specific runtime rule or hidden dependency knowledge was introduced.

Twenty variants split: EN six, PL eight, DE six. Forty use exactly the original
query. Enumeration/auxiliary-interrogative and implicit-dependency omissions
remain: S06/en model/media/entry, S10/en populate/publish, P02/en implicit checks,
and some `does/should/can` multi-part requests remain bundled. P03's configuration,
retained files and retention can share a focus; no four-part factual reference
decomposition was hardcoded. Full scope can dilute focus and does not prove
correct attachment of conditions to focused operations. All 60 plans and the
post-freeze limitation audit remain available, including cross-language asymmetry.

The equal10/equal20 conditions allocate exactly 10/20 **total raw result slots**
across all searches, original first. Merge round robin, retain native order,
apply cosine >=0.3 per search and deduplicate exact chunk IDs only. There is no
backfill, RRF, source/text/language dedup or reference-aware merging. Duplication
therefore reduces unique pools; this is part of the tested mechanism's cost.
Chunking, embedding model, cosine/index, scope and restrictions remain unchanged.
The optional expanded condition requests 20 per query, explicitly spending
68.33% more raw slots than single K20. Its gains are not pure decomposition gains.
Query vectors are shared across chunkers/budgets. A byte-verified disposable copy
of the original Chroma index was used; original indexes were never opened mutable.
Every distinct native search was repeated once and stable; all 240 original
K10/K20 control rankings, scores, source identities and ranges reproduce exactly.

# Candidate results

Positive coverage and completeness use 48 answerable variants. All 60 are retained
in costs, paired safety/restriction ledgers and diagnostics. Languages/families
are dependent; there is no significance or generalization claim.
""")
    data=[]
    for arm in ('B','C'):
        for cond in ('equal10','equal20','expanded20perquery'):
            s=summary[arm+'/'+cond];base=baseline[arm+'/K'+('10' if cond=='equal10' else '20')]
            data.append([arm,cond,f"{base['candidate_complete']}→{s['candidate_complete']}",
                f"{s['candidate_coverage']*100:.2f}%",len(s['gained_complete']),len(s['lost_complete']),
                f"{s['duplicate_slots']}/{s['raw_slots']}",s['unique_eligible']])
    parts.append(table(['Arm','Condition','Candidate complete before→after /48','After coverage','Complete gains','Complete losses','Duplicate / raw slots (60)','Unique eligible (60)'],data))
    parts.append("""
Single-query coverage is B/K10 53.99%, B/K20 65.97%, C/K10 55.56%, C/K20 60.76%.
The increased-budget condition raises B/K20 by only 0.35 points and C/K20 by
1.04 points, with complete counts unchanged at 25 and 24. No new complete set
is attributable to this decomposer, including with the larger budget.

Equal-budget complete losses are B/K10 P03-en and S12-en/de; B/K20 S13-pl;
C/K20 P03-en. C/K10 keeps its complete count but loses partial configuration,
WAL and MMU connection/path evidence. B's only new requirement family is partial
P03-pl summarizer configuration. Expanded C additionally gains P03-pl summarizer/
minimal-level support and S12-en metadata, still without a complete method.
P02 and S07/S11 remain incomplete. The full ledger includes all gains/losses/ties,
not just complete-case deltas or net warning totals.
""")
    parts.append(table(['Arm/condition','Requirements gained/lost','Critical gained/lost','Condition gained/lost','Restricted questions /60','New restricted rows'],[
        [key,f"{s['requirements_gained']}/{s['requirements_lost']}",f"{s['critical_gained']}/{s['critical_lost']}",
         f"{s['condition_gained']}/{s['condition_lost']}",s['restricted_questions'],s['new_restricted']] for key,s in summary.items()]))
    parts.append("""
Expanded B adds the restricted MK4S PDF-page-19 component to **S07-en** candidates.
No extraction witness credits it. This is candidate exposure, not a new production
or answer exposure; it remains an acceptance concern. All ten restrictions and
unresolved visual facts stay open. Product/version proof credit always requires
the exact frozen source identity; old APIs or another printer cannot substitute.
`unregistered_scope_neighbors` records every off-registry candidate/source for
all 360 comparisons. Such neighbors can be comparative context and do not
automatically establish factual product/version errors. Domain/bilingual
equivalence and partial registered proofs remain unresolved agent judgments.

# Extraction interaction: separate coherent libraries
""")
    parts.append(table(['Arm/condition','Candidate availability upper /48','Whole-chunk oracle /48','Sentence feasible /48','Paragraph feasible /48','Minimal-span feasible /48','New complete extracted sets vs same-budget single'],[
        [key,s['candidate_complete'],s['whole_complete'] if s['whole_complete'] is not None else 'not computed >20',
         *[s['extraction'][g]['complete'] for g in GRANULARITIES],
         '/'.join(str(len(s['extraction'][g]['gained_complete'])) for g in GRANULARITIES)] for key,s in summary.items()]))
    parts.append("""
Availability upper counts ignore source coherence/citation cost. The extracted
counts are constructive, source-exact lower bounds under the three separate
agent-reviewed envelope libraries; they are not label-free runtime gains.
Reference-informed library rules, citation model, missing closure ambiguity,
scope corrections and prior failed runs are documented in the extraction report.
No library is mixed with another or with a baseline fallback to inflate a bound.
The increased-budget whole-chunk oracle is deliberately uncomputed when pools
exceed its 20-candidate diagnostic bound; this does not affect candidate/extraction
results. No exact minimum is claimed for that missing cell.

No condition yields a newly available complete coherent extraction compared with
its corresponding original K10/K20 library, and **zero demonstrated cases require
both mechanisms**. Equal20 loses one extraction-complete case per arm (B S13-pl,
C S04-pl); the latter is a source-closure loss despite candidate-count accounting.
There is no new complete-proof availability to add to extraction's old ceiling.

The original incomplete-context partition remains: missing candidate proof affects
27/35 (77.14%) of incomplete B/K10 contexts and 27/30 (90%) of C/K10; at K20 it
affects 23/35 (65.71%) and 24/30 (80%). These are reference-relative bottlenecks,
not independent causal shares. This mechanism fails to repair them. Forty unsplit
variants are unchanged; split variants can lose prerequisites because duplicate
focused searches consume slots while the original query's depth is reduced.

P03-en is still the only extra candidate-complete case beyond the whole-chunk
budget ceiling. Necessary body text costs 499 tokens; coherent complete witnesses
cost 1,335–1,411, including exact versions, warnings and citation separators.
Feasibility below 1,000 remains unresolved; it is neither established nor proved
impossible. S13 fits 345–346 and S06 461–521 tokens, but both already had feasible
whole-chunk proofs. P02 missing sheet/bed proof, S07 tube proof, S11 MK4S-side
prerequisites and the 12 clarification/unavailable variants remain unresolved.
S12's frozen rubric-complete B packets fit whole chunks, while stricter complete
operational scope is absent from candidates; no old label was silently revised.
Retrieval completeness never certifies answer correctness.

# Architecture comparison and single recommendation

| Direction | Measured opportunity | Cost/risk and decision |
|---|---|---|
| Existing B/C | Reproducible original baselines | **Retain; production A unchanged** |
| Query decomposition | Zero new complete candidate sets; regressions at equal raw budgets | 41 query vectors, 101 vs 60 searches per chunker/condition; reject tested mechanism |
| Source-faithful extraction | S13/S06 token savings; no added complete case beyond whole oracle; P03 unresolved | Domain-sensitive scope, source/citation handling; review boundaries before runtime engineering |
| Combination | Zero new complete coherent sets in every library | Added complexity without measured completeness benefit; do not prioritize |
| Semantic reranking | Existing candidate order gaps remain | Prior BGE/GTE CPU K20 median overhead 27.74/12.44 s and regressions; absent candidates stay absent |
| Hierarchical/section-aware | Missing section discovery remains a bottleneck | Prior routing lost valid candidates, depended on distractor layout, showed no long-document gain; no automatic promotion |
| Larger context | Coherent P03 witnesses fit above 1,000 | Cannot repair absent candidates; no generation-quality evidence; not a default change |

**Primary recommendation: no architecture change or new engineering experiment
now.** Domain/source-boundary adjudication is the next prerequisite. This rejects
the tested mechanism, not the general research topics. Do not repeat rejected
FTS5/RRF, lexical/redundancy selector objectives or this focus strategy under new
names. A future genuinely different mechanism needs a frozen development result
before the approximately 24 new intent-family holdout is created. That holdout
was not generated here; all present questions remain exposed development data.

# Reproduction, tests and preservation
""")
    parts.append(f"External package: `{package}`.\n\n")
    parts.append("""
`decomposition/` preserves the pre-label mechanism/workload freeze;
`embeddings-authorized/` records the exact approval, weight/catalog compatibility,
six dispatch receipts, 41 vectors and job snapshot. `decomposition-retrieval/`
has sealed native rankings, 240 controls, search receipts and provenance;
`decomposition-scores/` has all 360 reference evaluations and complete extraction
witnesses. `completed-reports/` has the all-60 CSV, every requirement/safety/
restriction gain/loss/tie, language strata and nonadditive combined bounds.
Original pre-authorization reports and all rejected/intermediate runs remain
preserved. The main extraction oracle is `analysis-v3/`.

Reproduce offline with `scripts/run_isolated.py --keep-diagnostics eval
laew.eval.decomposition_retrieval_study collect --package <package> --output fresh`,
then `score --package <package> --retrieval <saved-collection> --output fresh`.
Collection reuses the 41 approved cached vectors and performs no new inference.
Copy retained work outputs into fresh external directories in the same shell
call. `laew.eval.fine_evidence_report --completed --package ... --output fresh`
rebuilds these final reports. Do **not** rerun the authorized embedding job for
reproduction; use its sealed cache. Socket access is blocked in offline analysis.

Tests and integrity receipts are recorded in `final-verification.json`; relevant
new contracts and frozen retrieval/scoring acceptance use `scripts/run_isolated.py`.
No original sources, questions, rubric, saved A/B/C or rejected results changed.
No production RAG, model answer, Luna inference, LLM judge, corpus rebuild,
independent holdout or Git add/commit/push/reset/clean occurred.
""")
    (output/DECOMPOSITION_REPORT).write_text('\n\n'.join(parts),encoding='utf-8')
    # Retain the detailed extraction methodology but update its recommendation
    # around the completed authorized comparison, not abandoned planning advice.
    text=(package/'reports-final'/EXTRACTION_REPORT).read_text(encoding='utf-8')
    start=text.index('# Decision and evidential limits');end=text.index('# Verification and isolation')
    text=text[:start]+"""# Decision and evidential limits

**Retain A/B/C; reject the tested query-focus decomposition and do not prioritize
their combination.** The separately authorized 41-query embedding job and full
retrieval comparison are complete in the companion decomposition report. No
equal-budget or increased-budget condition discovers an additional complete
candidate set; every extraction library has zero newly complete combined sets.
The primary next-step recommendation is no new architecture engineering until
source-boundary/domain judgments are resolved. Earlier pre-authorization
recommendations are preserved externally as history, not current advice.

Extraction saves tokens in proven source-bound examples, but the incremental
complete-case ceiling beyond whole chunks is only one P03-en case in B/K10,
B/K20 and C/K20, and zero in C/K10. P03-en requires at least 499 body tokens
before scope/citations; a complete conservative witness costs 1,335 minimal-span,
1,337 sentence or 1,411 paragraph tokens. The global coherent minimum is only
bounded at **499–1,335** under the most permissive admitted library. Fitting all
six requirements below 1,000 is unresolved, not proved feasible or impossible.
This diagnostic does not establish a label-free extractor or answer correctness.

"""+text[end:]
    # Replace the pre-authorization architecture decision block as a whole.
    start=text.index('# Combined potential and architectural decision');end=text.index('# Artifacts and reproduction')
    text=text[:start]+"""# Combined potential and architectural decision

The companion completed decomposition report provides the final equal-budget,
increased-budget, safety/version and combined tables. Missing candidate proof
accounts for 77.14% / 90% of incomplete B/C K10 contexts, but the tested syntactic
focus mechanism adds no complete pool and introduces regressions. No extraction
library gains a newly complete combined set; no proven case requires both tested
mechanisms. Bounds are not summed across overlapping cases or libraries.

Retain existing B/C and production A. The primary next step is no new architecture
engineering experiment before source-boundary/domain adjudication. The measured
token savings justify that review, not deployment. Previous CPU reranker latency/
regressions, rejected FTS5/RRF and lexical selectors, and hierarchical routing's
layout sensitivity remain reasons against automatic complexity. Larger context
can hold a 1,335-token P03 witness but cannot supply absent candidates. None of
these findings certifies answer correctness, significance or generalization.
The independent ~24-family holdout remains uncreated.

"""+text[end:]
    text=text.replace('four evaluation-only modules, one test module','six evaluation-only modules, two test modules')
    text=text.replace('scope: 60 exposed development questions; 48 answerable; no inference',
                      'scope: 60 exposed development questions; 48 answerable; extraction offline; 41 query embeddings separately authorized')
    text=text.replace('Validation: **67 tests passed, zero skipped**','The pre-authorization extraction validation had **67 tests passed, zero skipped**')
    text+='\nThe completed authorized comparison, final test count and full file inventory are recorded in the companion report and final validation receipt.\n'
    (output/EXTRACTION_REPORT).write_text(text,encoding='utf-8')
    seal(output,[p.name for p in output.iterdir() if p.is_file()],reporter_sha256=sha(__file__))
    print(dict(output=str(output),comparisons=len(rows),additional_complete_sets=0,decision='no-change; reject frozen decomposition'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--completed',action='store_true')
    args=parser.parse_args()
    with offline():
        (build_complete if args.completed else build)(args.package,args.output)


if __name__=='__main__':
    main()
