---
title: Stage 3C.3 — Offline scorer repair and answer adjudication
date: 2026-11-15
status: completed-post-result-agent-adjudication-human-review-pending
scope: existing 36 answers only; evaluation code and annotations; no model work
---

# Result

The repaired answer scorer processes **all 36 saved answers**, eliminating the
**11 applicability exceptions** without changing rubric v2.1, any answer,
delivered context or retrieval setting. Its 25 previously computed diagnostic
outputs are unchanged apart from new applicability-provenance fields. Frozen
context-evidence scores remain identical for all 36 cases.

This work is **`post_result_agent_adjudication`**. The same exposed agent
reviewed original annotations and outcomes. No independent human reviewer,
approval, agreement statistic or new model behavior is claimed. There were
**zero inference, judge, retrieval, embedding or catalog requests**. Network
access is intercepted and forbidden in the replay and its tests.

The repair is ready for offline reviewer-assisted use. The complete evaluation
method is **not yet reliable enough to select B/C or certify automated answer
quality for a next development experiment**: historical annotation gaps and
specific source-entailment disputes still require adjudication. Do not treat
removing a scorer exception as confirming the answer.

# Integrity and historical preservation

Before editing, verified the full historical live package (90 inventoried
files), its raw-answer/ledger manifest (37 members), the 777-file corpus,
pilot/sealed manifests, 201 retrieval artifacts, the audit/calibration packages,
the rejected delivery package, original request/trace fixtures and 112
source/version-bound atoms. No dataset, question, source snapshot, answer or
original annotation/result was changed. The initial working tree was clean.

| Trust anchor | SHA-256 |
|---|---|
| Historical live artifact manifest | `29ae7000c7f534127147bf221d54b34b3d0aa9f78c6cc27e0bbae8756d4ec6dc` |
| Historical raw-answer manifest | `0ce969d191fa5a5bc552e2ac2724a50a1710ea4892471677c2c030bce44c8636` |
| Effective v2.1 rubric manifest | `36f985c702203012166f99b5a53850acea6e77f5d80ef25c0514dcdec870cee3` |
| Unchanged rubric JSON | `205c7a58dba52c413eb29733dacfc4f470786e00142f1db30bd0d3de805efb33` |
| Historical scorer snapshot | `b0f7a8bc72645957f084398b8002fc8937c15b5d29014212954cbdf582ac3330` |
| Repaired evaluation scorer | `47bbe6152657c336b1d319739569cf4585dc9c3c0f01a6fe8dd8fc0ef30e3d2c` |

The old scorer was copied byte-for-byte into the new external package and
loaded separately for replay. Original manifest pins were not edited to accept
the repaired code. The old live runner intentionally still requires its
historical scorer fingerprint; do not relax that gate or use this repair to
start more inference.

All ten source restrictions, 329 uninspected High findings and other inherited
risks remain open. Targeted offline inspection of the existing MINI+ PDF-page
42/43/44 rasters checked publisher prose only; it did not clear a page, diagram,
icon relationship or previously unavailable component. Their frozen hashes and
source mappings remain the evidence authority.

# Root cause of the eleven conflicts

`score_evidence` uses `method.conditions` to enumerate hypothetical evidence
scenarios. The old `score_answer` also compared those values with actual
reviewed answer conditions and rejected any difference. It therefore treated
an evidence scenario's false defaults as prohibitions on additional advice.
There were **19 conflicting condition cells across 11 answers**, all false
method assumptions versus true reviewed conditions.

| Cases | Count | Reviewed condition rejected by the old scorer |
|---|---:|---|
| P02-en/C | 1 | Conditional cleaning advice added to a no-cleaning evidence scenario |
| P03-en/A and B | 2 | Checksum-change discussion added to the minimum scenario |
| P04-de/A/B/C, P04-en/A/B/C, P04-pl/B/C | 8 | Version comparison and conditional replacement-configuration guidance added to the minimum clarification scenario |

These were neither question contradictions nor evidence of incorrect model
versions. The original rubric's required fact sets, alternative methods,
conditions and invariants were not revised.

# Minimal evaluation-only correction

The answer scorer now derives applicability from the question-fixed conditions
and explicit reviewer observations; it does not import evidence-scenario
defaults. The chosen method's required facts and all technical invariants still
apply. `score_evidence` is unchanged.

`answer_conditions` supports optional, exact-quote-bound scoped decisions:

| Category | Treatment |
|---|---|
| Question-fixed fact | Immutable; a conflicting review value or claim trigger still fails closed. Version/unit/negation invariants continue to reject wrong claims. |
| Actual recommendation | Activates the corresponding requirements. A recommendation conditional on a user circumstance activates that branch's safeguards without asserting that circumstance is established. |
| Relevant technical explanation | Activates a content-based trigger, such as discussion of checksum-change limitations or a version comparison. This does not automatically recommend a different procedure. |
| Mere hypothetical mention | Does not activate a procedure when the reviewer explicitly establishes it is not being advised. A conditional instruction is not automatically a mere mention. |
| Unknown/unresolved | Remains null. Neither a false nor true method assumption fills the gap. Unresolved applicability blocks completeness and safety passes. |

New scoped decisions require a known kind, rationale, complete coverage of the
unfixed condition keys, and bound answer quotes for positive/explanatory or
hypothetical observations. Invalid or contradictory annotations fail closed.
Legacy boolean reviews can be replayed, but their missing scope provenance is
reported in `condition_review_gaps`; it is not invented from keywords. The new
overlay explicitly documents all **81 answer-dependent condition decisions**.

This is not an automatic semantic classifier. Reviewers must distinguish a
conditional recommendation from a hypothetical mention. Safety requirements
remain active for actionable advice even when an answer says “if”. Existing
question constraints and incorrect technical invariants are still enforced.

# Adjudication of the saved answers

All 36 answer/context pairs were inspected, using frozen originals, source-bound
atoms, exact dispatched bodies, existing annotations and v2.1 minimum criteria.
The separate overlay records whether a disputed historical judgment is
supported, incorrect or unresolved; exact source evidence stays outside Git.

**P01:** retain all core completeness judgments. Optional getter commands are
not required, but their correctness does not give them delivered support.
The three existing getter-related grounding losses remain. The B/en locator
combines an existing filename with the wrong heading; C/en cites a passage that
does not entail precedence. Keep these citation defects separate from core
factual correctness and evidence elsewhere in the delivered context. No
additional filename, system-precedence explanation or alternative command is
made mandatory.

**P02-pl/A and B:** the old confirmed-error classification overreached. An
instruction for this replaced sheet is not an explicit claim that solvent
cleaning is necessary before every print. Whether this particular replacement
requires that preparation is still unresolved; the supplied accessories or
first-print checklist do not settle it. Replace the asserted universal factual
error with unresolved necessity/scope. Retain incomplete minimum answers,
unsupported scope and every activated cleaning/IPA safeguard omission. This
does not endorse the unqualified cleaning advice as safe.

**P02-pl/C:** the answer specifies first-layer/Live Z calibration, not complete
initial printer recalibration. The original publisher callout applies its
first-layer observation/nozzle-gap instruction whenever sheets change, including
no restriction to different sheet types. Provisionally accept this as a valid
first-layer procedure under the existing criterion. The actual delivered 9.6
fragment discusses different sheet types and does not establish the entire
same-smooth-sheet extension, so it still loses full delivered grounding. The
answer also still misses other minimum requirements. Human domain confirmation
of this procedural equivalence remains requested.

**P03-en/A and B:** upgrade the checksum warning from partial to complete. The
frozen registered checksum atom is itself a general caution about changed
checksum status with a reference to limitations. Both answers convey that
proposition. Requiring reproduction of the unfrozen linked manual's details
exceeded v2.1. Keep the discussion trigger active; correct the coverage judgment
instead of waiving a warning. Both answers remain incomplete overall.

**P03 summary-range grounding:** apply the same standard to A/en and B/en.
Neither delivered body contains the full registered LSN-interval definition.
B also describes changed blocks, so the admissible inference from its extra
text needs domain adjudication. Mark the disputed range entailment unresolved
in both arms. This moves B/en's earlier full-grounding assertion to an unresolved
status, an unfavorable change for B. It also stops presenting A/en's analogous
negative entailment judgment as conclusively settled. The conservative count
excludes both; an upper count includes each if the open dispute is accepted.

**Other P03 cases:** retain missing configuration/manifest/retention/chain and
WAL-history requirements where absent or partial. No restore execution procedure
is inferred merely from a retained-file list. Keep P03-pl/A's extensive
delivered-support failure: most of its plausible technical material is absent
from its dispatched body. Its absolute historical-summary irrecoverability
claims remain unresolved, not conclusively false merely because unsupported.
No complete P03 answer emerges from this audit.

**P04:** all nine answers require the actual target-server major version.
Normal configuration guidance conditional on a newer version is actionable
decision guidance, so its startup prohibition remains applicable. The omissions
in P04-de/A, P04-en/A and P04-en/B are preserved. The other conditional procedures
are not penalized just for being conditional. P04-pl/A's bounded older-version
explanation plus clarification is sufficient; a complete tutorial for every
version is not required. Its minimum denominator stays different because it
does not give the optional newer-version procedure.

# Original versus corrected provisional results

Each arm still has 12 completed answers. The values below are disclosed
group-level agent judgments, not strict automated validated passes.

| Endpoint, original → adjudicated | A | B | C |
|---|---:|---:|---:|
| Correct and minimally complete | 4 → 4 | 5 → 5 | 6 → 6 |
| Correct, minimally complete and fully grounded | 3 → 3 | 5 → 5 | 4 → 4 |
| All substantive assertions context-grounded | 7 → 7–8 | 9 → 8–9 | 8 → 8 |
| Missing any applicable critical requirement | 8 → 8 | 7 → 7 | 6 → 6 |
| Missing answer-triggered conditional safeguards | 4 → 3 | 3 → 2 | 1 → 1 |
| Confirmed unsupported-claim answers | 5 → 4 | 3 → 3 | 4 → 4 |
| Additional unresolved support cases | 0 → 1 | 0 → 1 | 0 → 0 |
| Full active requirement assertions | 14 → 15 | 16 → 17 | 19 → 20 |
| Confirmed procedure-overgeneralization errors | 1 → 0 | 1 → 0 | 1 → 0 |
| Unresolved factual/necessity cases | 1 → 2 | 0 → 1 | 0 → 0 |

Ranges describe only the identified entailment disputes, not statistical
confidence intervals or comprehensive uncertainty bounds. All agent judgments
remain subject to independent review. Removing a confirmed-error label in
favor of unresolved does not mean an answer is proven correct. Counting
confirmed plus unresolved support failures gives 5/12, 4/12 and 4/12 for A/B/C.
The complete `score-deltas.json` includes all changed scalar/list/dimension
scores; `question-comparison.json` covers every question/arm, including ties.
The three additional complete requirements concern checksum cautions in A/B
and the first-layer criterion in C, not an improved minimum-answer threshold.

The **B-versus-C interpretation does not reverse** on the provisional
correct/complete/grounded endpoint (5 versus 4), but the broader claim that B
has more fully grounded answers becomes uncertain (B 8–9 versus C 8).
This is a methodological correction to the same responses, not new model
behavior. It weakens confidence in selecting a configuration from this pilot.
The four shared intent families, language dependence and one sample per cell
still prevent a significance or general superiority claim. Production A stays
unchanged; no configuration is deployed or newly optimized.

# Strict replay and remaining annotation limitations

Repair-only replay uses exactly the original saved review objects: 11 rejected
combinations become computed diagnostics, while the other 25 score objects are
unchanged except for applicability provenance. The scoped overlay replay also
computes all 36. No exceptions are converted to a pass by ignoring conditions.

**All 36 strict deterministic answer diagnostics still report unresolved
correctness.** Historical reviews used short requirement selectors plus large
unregistered substantive spans marked unresolved. The present minimal repair
does not invent missing atomic semantics, relabel those spans nontechnical or
change the scorer's claim-to-proof registry. Thus these diagnostics are not
the same estimand as the provisional group-level counts above. A future complete
claim partition is required before calling the end-to-end metric automated and
validated. The issue is recorded explicitly for every row.

Priority human work comprises six domain-dispute cases (P02-pl A/B/C,
P03-en A/B, P03-pl/A), the original nine P04 second reviews, the P01
getter/locator cases and completion of quote-bound claim annotations for all
36 answers. Do not overwrite an agent origin with human approval. A reviewer
who reveals these drafts must disclose that exposure.

The compact local HTML form lists priority cases first, retains all 36 exact
answers/contexts and frozen source criteria, hides proposals until requested,
and exports unadjudicated manual judgments. The original review form remains
immutable. No new question or generated answer is included.

# Artifacts, tests and reproduction

New external versioned package:

`C:\Users\korne\.codex\visualizations\2026\11\15\01a1e05d-6573-7bf1-b706-6d9499db2672\laew-scorer-adjudication-v1`

- `historical/scoring_calibration_v2_1.py`, `input-integrity.json` and
  `initial-state.json`: immutable parent pins and initial verification.
- `results-v3/`: authoritative root causes, original/repair/scoped replay,
  adjudication overlay, all score deltas, source evidence, question comparison,
  summary and human-review queue. Earlier internal versions are retained.
- `manual-review-v2/answer-adjudication.html`: local manual package;
  `blank-adjudication.json` is an unfilled portable alternative.
- `adjudicate.py`, `render_adjudication_review.py`, code snapshots, validation
  receipts, test log and artifact manifest: reproducibility and integrity.

Reproduce offline using the repository venv:
`adjudicate.py <fresh-output-directory>`. It forbids socket connections and
Requests transport access, verifies historical manifests, loads the pinned old
scorer and checks that context scores remain identical. Existing outputs are
never overwritten. Do not invoke any live runner.

**37 tests passed, zero skipped**, through `scripts/run_isolated.py`: existing
calibration tests, fifteen synthetic condition-regression cases covering all
five requested categories, and three immutable 36-answer replay checks. They
cover genuine question contradictions, invalid scope/quote evidence, unknown
conditions, hypothetical mentions, conditional recommendations, warnings,
incorrect versions, legacy provenance and unchanged evidence scoring.

Repository changes are evaluation-only `scoring_calibration.py`, two new test
modules, this metadata-only report and an additive documentation-index entry.
Historical reports and all original artifacts stay intact. Final validation,
hashes and Git status are in the external package. No Git add, commit, push,
reset or clean was executed. No production RAG, A/B/C setting, context selector,
embedding service or model integration was modified.

**Hard stop:** finish with the offline review package. The next prerequisite is
domain/claim-level adjudication, not another retrieval experiment or inference
run. No new experiment is started by this recommendation.
