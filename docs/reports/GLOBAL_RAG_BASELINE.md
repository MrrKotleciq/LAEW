---
type: report
title: Global RAG Correctness and Retrieval Baseline
scope: Stage 2B.1 context budgeting, Obsidian metadata, and bilingual retrieval
read_when:
  - Reproducing the vector retrieval baseline
  - Comparing the current chunker with a candidate implementation
---

# Global RAG Correctness and Retrieval Baseline

The Stage 2A audit is the historical reference. Stage 2B.1 keeps vector ranking, the existing heading and character chunker, and the manifest embedding model. Knowledge Curation still requests the existing scope synchronization after an approved write.

The context builder now budgets the rendered string, including source paths, headings, metadata labels, separators, and truncation markers. If a header leaves no usable text, the builder skips that chunk. An oversized first fitting chunk contributes only the visible excerpt to the result. `total_tokens` is the ceiling of rendered Unicode character count divided by four. This heuristic is not a guarantee about the downstream model tokenizer or the size of the complete serialized tool response.

The note parser uses safe YAML with a compatibility fallback for malformed legacy frontmatter. The retrieval metadata exposes `name`, `description`, `title`, `type`, `scope`, `status`, `tags`, and `read_when` when valid and present. Chroma encodes structured metadata as JSON and decodes it on retrieval. Note `scope` is descriptive. The actual source scope still comes from the trusted ingestion root and retrieval boundary. The context displays type and status, and RagTool returns the complete allowlisted properties as `source_metadata`. Source Markdown, wikilinks, and Breadcrumbs fields remain on disk. Wikilink targets are retained, but Breadcrumbs relations are not resolved into a graph. Draft, research, and unverified notes remain eligible. An ordinary synchronization can refresh affected legacy index records. This work did not run it against production.

## Reproduce

From the repository root, with the manifest embedding service running and ChromaDB installed in the project environment:

```powershell
.venv/Scripts/python.exe -m laew.eval.rag_baseline --output global-rag-run.json
```

The output path must be new. The runner copies only the selected benchmark fixture into temporary project and global roots. It creates a temporary Chroma PersistentClient database and does not use the manifest Chroma server, conversation storage, scheduler, or Memory. The embedding probe checks the configured service before indexing and a failed request aborts the measurement. The benchmark records dataset and corpus hashes, model ID, endpoint, declared dimensions, Chroma version, retrieval settings, grouped scores, per-query results and elapsed time.

The frozen v1 dataset contains 28 queries, 14 in each language, over nine global notes and one private project decoy. It includes 14 cross-language cases based on evidence document language, four multi-document questions and four no-answer cases. The judgments identify required paths and exact supporting passages with section names. Grade 2 means required evidence, grade 1 means related background, and unlisted paths are grade 0. The dataset hash test ignores platform line endings. Preserve the labels when comparing implementations and version any expansion separately.

## Observed baseline

The [structured result](global_rag_baseline_v1.json) uses the live local `laew-qwen3-embedding` endpoint, 1024 dimensions, top-k 5, threshold 0.30 and 1000/200 character chunking. Chroma ran in an isolated database. Ranking metrics cover the 24 answerable queries. The five positions in Precision@5 are fixed, and duplicate chunks from one document occupy one document rank after retrieval. Recall uses required documents, while precision, MRR and nDCG use all positively graded documents. Source correctness checks returned paths against the fixture. Evidence coverage requires a matching path, section and visible passage. No-answer behavior is the fraction with zero returned chunks.

| Group | Document Recall@5 | Precision@5 | MRR | nDCG@5 | Evidence coverage |
|---|---:|---:|---:|---:|---:|
| Answerable queries | 1.000 | 0.242 | 0.931 | 0.945 | 97.9% |
| Polish | 1.000 | 0.233 | 0.958 | 0.969 | 95.8% |
| English | 1.000 | 0.250 | 0.903 | 0.921 | 100% |
| Cross-language | 1.000 | 0.271 | 0.881 | 0.906 | 96.4% |
| Multi-document | 1.000 | 0.400 | 1.000 | 0.980 | 87.5% |

All returned source paths resolved to fixture documents and no query exposed the private project note. One of four no-answer queries returned no chunks. Query `q19` retrieved both required documents but missed the `Akceptacja` section in `vault.md`. Two independent fresh indexes produced identical results and configuration, excluding total duration (9.68 and 9.22 seconds). The corpus is too small to infer production quality, and these metrics cover retrieved evidence rather than Chief Agent answers or abstention.

## Proposed Stage 2B.2 experiment

Compare a fence- and table-aware chunker with heading ancestry against the current implementation in separate disposable indexes. Keep the v1 dataset, embedding endpoint, top-k and similarity threshold fixed. Add a separately versioned stress set for long fenced commands, wide tables, nested headings and evidence spanning a split. Track passage coverage by section, with special attention to cross-language and multi-document queries, and check source isolation and no-answer false positives. Record chunk count and indexing time along with context size and query latency. Treat the short v1 corpus as a regression guard. It has limited power to distinguish chunkers at document level because Recall@5 is already saturated.
