# Hard-case evaluation v1

The corpus and evidence atoms were written before implementing structure-v2.
Four development queries and nine validation queries (including two no-answer
cases) are recorded in dataset.json. The validation results were not used to
retune the strategy. This is a small synthetic technical corpus, not a claim
about production quality or independent external validation.

Each evidence atom is a literal source passage with a trusted document path.
Coverage requires every atom, including descriptions, restrictions and values;
matching a document alone does not imply evidence coverage. Atoms may appear
in separate returned chunks. Complete evidence is reported separately. Heading
labels are intentionally not required for this new dataset, while the frozen
baseline retains its original section-aware judgments. Compare strategies
within each corpus, not absolute scores across these two scoring conventions.

Run all three strategies at top-k 5 and repeat at top-k 1 to expose sensitivity
to candidate count. Top-k 1 is a diagnostic, not a proposed runtime setting.
The benchmark never uses production Chroma or production knowledge roots.
Regenerate only deliberately with tests/rag/build_hard_cases_v1.py; the hash
is locked in tests/evaluation/test_contextual_evaluation.py.

Example (use a new output filename and an isolated writable TEMP directory):

```powershell
.venv/Scripts/python.exe -m laew.eval.rag_baseline --dataset tests/rag/hard_cases_v1 --strategy structure-v2 --top-k 5 --output hard-v2-new.json
```

Repeat with legacy/structure-v1 and with --top-k 1. Each invocation constructs
only a disposable local Chroma database; it calls the configured embedding
service, so run only when that endpoint is authorized and available.
