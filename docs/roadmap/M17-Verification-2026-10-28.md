# M17 verification — 2026-10-28

Historical status at this verification stage: **in progress**. M17 was completed
after approved production-vault deployment on 2026-10-29; see
[the current acceptance matrix](M17-Knowledge-Preparation-2026-10-29.md).
The dated evidence below is preserved as the earlier snapshot.
This record distinguishes the milestone's definition
of done from integration and operational checks. Runtime reports are local,
Git-ignored evidence and may not exist in another checkout.

| Requirement | Source | Evidence | Missing evidence | Status |
|---|---|---|---|---|
| Real populated, curated global vault | M17 scope and Definition of Done; ADR-002 | Read-only inspection: one synthetic `test-global-knowledge.md` in `C:\ROOT\Knowledge` | Cross-project engineering knowledge organized as described by M17 and retrievable from the actual vault | Not met |
| Project and global separation and attribution | M17 tests; ADR-011 | Isolated live project A/B, global and hybrid queries in `runtime/m17-validation-e1e30ef7467f/report.json` | Validation of actual curated vault contents | Fixture pass |
| Vault ingestion and link preservation | M17 tests | `tests/unit/test_m17_obsidian_ingestion.py`; focused tests passed | Validation against populated real vault | Fixture pass |
| Incremental synchronization and restart freshness | M17 implementation notes | Isolated live report; process coordination integration tests; browser retrieval after Workbench process restart | None for tested paths | Pass for tested paths |
| Interrupted synchronization recovery | M17 implementation notes | `tests/integration/test_rag_http_crash.py`: real HTTP server, confirmed partial write, lock release, incomplete marker, blocked retrieval and repair | None for tested single-host scenario | Pass |
| Chief Agent and Workbench integration | Implementation integration check | Four successful live model queries and tool/source events in isolated report. On 2026-10-29, the isolated browser returned project A and global codes with both Sources, then project B's own code; after restarting the isolated Workbench and Chroma as new processes, project A retrieval succeeded. | None for these tested paths | Pass for tested paths |
| Failure handling | Freshness safety in M17 implementation notes | `runtime/m17-validation-109721e3cd81/report.json`: live Chief Agent observed failed RagTool results for embedding synchronization failure, stopped HTTP Chroma, and incomplete marker; both repaired cases retrieved the current code. Healthy global retrieval remained available during the simulated project embedding failure. On 2026-10-29, an isolated browser displayed the RagTool connection error and the model reported retrieval failure without guessing. | None for these tested paths | Pass for tested paths |

M17 does not specify automatic curation, a minimum document count, an exact
metadata schema, or a mandatory migration of a particular existing corpus.
The named vault organization and populated curated source are explicit; a
single synthetic test note cannot establish that definition of done. Do not
alter the production vault or its collections as part of validation.

Full Auto/Manual/Restricted and approval-decision coverage belongs to the
Workbench permissions backlog. Broader terminal execution belongs to the
TerminalTool backlog. Monitoring, telemetry, backups and retention belong to
M18. These are not additional M17 acceptance criteria.

The Workbench synchronization label reports the last synchronization outcome;
it still showed success after the test server was stopped, even though the
subsequent retrieval correctly failed. A live availability indicator would be a
separate UX improvement and is not evidence of a successful retrieval.

Current-run verification: `pytest tests/unit tests/integration -m "not ollama"
-q` reported 826 passed, 2 skipped, 1 deselected; a focused RAG/process/agent/
Workbench/provider run reported 137 passed; `node --test tests/ui/*.test.js`
reported 9 passed after adding the long Unicode stream regression;
`node --check laew/ui/app.js` and `git diff --check` passed.
The broad and focused runs both include the HTTP crash regression. Warnings
included ChromaDB deprecations and unclosed
socket ResourceWarnings during the focused run.
An independent `pytest tests/integration -m "not ollama" -q` run reported
56 passed and 1 deselected.

## Unicode diagnostics

The apparent replacement characters printed by the terminal in the earlier
failure report were checked against the stored JSON as Unicode code points:
the characters were U+2014 em dashes, not U+FFFD. In the repeated failure
scenario `runtime/m17-validation-2f38978f630e`, the same live-model answer was
present in the captured provider SSE bytes and backend stream, with valid UTF-8
and no U+FFFD. Existing regression tests independently exercise provider SSE
and browser NDJSON with split multibyte characters, as well as Markdown
rendering; the new byte-by-byte NDJSON test includes Polish characters, dashes,
typographic quotes, emoji, and long Markdown. A shorter live browser response on
2026-10-29 displayed the Polish alphabet, both dashes, typographic Polish quotes,
emoji, and Markdown list; provider SSE and Workbench NDJSON contained the same
answer without U+FFFD, and browser DOM text matched after Markdown rendering.
The model emitted ASCII English quotes despite being asked for typographic
English quotes. A longer live attempt was cancelled when the model attempted
unnecessary tools; it does not prove the complete long-response flow. The tests
do not establish the origin of every previously observed replacement character;
no renderer change is justified by these observations.
