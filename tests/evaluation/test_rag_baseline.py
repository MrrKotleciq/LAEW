"""Regression coverage for Stage 2B.1 retrieval correctness and frozen labels."""
import hashlib
import json
import math
from types import SimpleNamespace

import pytest

from laew.eval.rag_baseline import DEFAULT_DATASET, evaluate, score_query
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import ChromaVectorStore, DocumentChunk


def chunk(name="note.md", text="A paragraph.", source="global", section="Evidence"):
    return DocumentChunk(name, text, source=source, file_path=name,
                         metadata={"section_header": section})


@pytest.mark.parametrize("budget", [0, 1, 8, 24, 50, 100])
def test_context_counts_rendered_attribution_and_unicode(budget):
    pipeline = RAGPipeline(None, None, max_context_tokens=budget)
    text = "Zażółć gęślą 🧪 — a long English sentence. " * 100
    context, used, tokens = pipeline._build_context([
        (chunk("x" * 500 + ".md", text), 1),
        (chunk("valid.md", text), .9),
    ])
    assert tokens == math.ceil(len(context) / 4)
    assert tokens <= budget
    assert "xxxx" not in context
    if budget >= 24:
        assert len(used) == 1
        assert "valid.md" in context and "🧪" in context
        assert used[0][0].text in text and context.endswith("...")
    else:
        assert context == "" and used == []
    assert pipeline._build_context([]) == ("", [], 0)


def test_context_counts_separators_and_skips_non_fitting_sources():
    pipeline = RAGPipeline(None, None, max_context_tokens=36)
    context, used, count = pipeline._build_context([
        (chunk("first.md", "Pół sekcji."), 1),
        (chunk("second.md", "A second section."), .9),
        (chunk("third.md", "A third section."), .8),
    ])
    assert [item.file_path for item, _ in used] == ["first.md", "second.md"]
    assert context.count("\n\n---\n\n") == 1
    assert count == math.ceil(len(context) / 4) <= 36


def test_metric_values_and_scope():
    query = {"allowed_scope": "global", "no_answer": None,
             "expected_document_ids": ["@knowledge/a.md", "@knowledge/b.md"],
             "relevance": {"@knowledge/a.md": 2, "@knowledge/b.md": 2, "@knowledge/c.md": 1},
             "evidence": [{"document_id": "@knowledge/a.md", "section": "Evidence", "passage": "part A"},
                          {"document_id": "@knowledge/b.md", "section": "Evidence", "passage": "part B"}]}
    known = {"@project/private.md", "@knowledge/a.md", "@knowledge/c.md"}
    results = [(chunk("private.md", source="project"), 1), (chunk("c.md"), .9),
               (chunk("a.md", "part A"), .8), (chunk("a.md", "duplicate"), .7)]
    score = score_query(query, results, known)
    assert score["recall_at_5"] == .5
    assert score["precision_at_5"] == .4
    assert score["reciprocal_rank"] == .5
    assert score["ndcg_at_5"] == pytest.approx((1/math.log2(3) + 3/2)/(3 + 3/math.log2(3) + 1/2))
    assert score["evidence_coverage"] == .5
    assert score["source_correctness"] == 1
    assert score["scope_isolated"] is False
    assert score["all_required_documents"] is False
    absent = query | {"no_answer": "out_of_scope"}
    assert score_query(absent, results, known)["no_answer_empty"] is False
    assert score_query(absent, [], known)["no_answer_empty"] is True


def test_frozen_dataset_and_repeatable_grouping():
    raw = (DEFAULT_DATASET / "dataset.json").read_text(encoding="utf-8").encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == "cbb337883bb34e2b5ae21502a763471d20b4a93b1f278d52c06b24243950370d"
    data = json.loads(raw)
    assert len({q["id"] for q in data["queries"]}) == len(data["queries"]) == 28
    for query in data["queries"]:
        for item in query["evidence"]:
            path = DEFAULT_DATASET / "global" / item["document_id"].removeprefix("@knowledge/")
            content = path.read_text(encoding="utf8")
            assert f"## {item['section']}" in content and item["passage"] in content
    fixture = SimpleNamespace(retrieve=lambda *a, **kw: SimpleNamespace(error=None, chunks=[]))
    report = evaluate(fixture, data, set())
    assert report == evaluate(fixture, data, set())
    assert report["categories"]["language:pl"]["query_count"] + report["categories"]["language:en"]["query_count"] == 28
    assert report["categories"]["cross_language"]["query_count"] >= 8
    assert report["categories"]["no_answer"]["query_count"] == 4


def test_chroma_filter_fallback_still_rejects_wrong_scope():
    def query(**options):
        if 'where' in options:
            raise TypeError('legacy client does not support where')
        return {'ids': [['private', 'public']], 'distances': [[0, .1]], 'metadatas': [[
            {'source': 'project', 'text': 'Private calibration'},
            {'source': 'global', 'text': 'Public guide'},
        ]]}

    store = object.__new__(ChromaVectorStore)
    store.source = None
    store._collection = SimpleNamespace(query=query)
    assert [item.chunk_id for item, _ in store.search([1., 0.], source_filter='global')] == ['public']
