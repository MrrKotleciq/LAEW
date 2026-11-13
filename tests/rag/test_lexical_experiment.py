"""Safe query semantics, isolation, persistence and synchronization regressions."""
from copy import deepcopy
import importlib.util
import json
import sqlite3

import pytest

from laew.rag.lexical_experiment import BM25SIndex, Binding, FTS5Index, match_expression, query_terms, tokenize

BACKENDS = [FTS5Index, pytest.param(BM25SIndex, marks=pytest.mark.skipif(
    importlib.util.find_spec("bm25s") is None, reason="Optional pinned BM25S experiment dependency"))]


def record(identifier, text, source="global", path="guide.md", **metadata):
    return {"id": identifier, "text": text, "source": source, "path": path, "metadata": metadata}


@pytest.fixture(params=BACKENDS)
def index(request, tmp_path):
    instance = request.param(tmp_path / "index", Binding("fixture", "global"))
    try:
        yield instance
    finally:
        instance.close()


def ids(index, query, k=20):
    return [h.record["id"] for h in index.search(query, k)]


def test_shared_tokenization_identifiers_symbols_diacritics():
    assert tokenize("sample_rate net.http C++ C# foo::bar --no-commit R7 80µs") == [
        "sample_rate", "net", "http", "c", "c", "foo", "bar", "no", "commit", "r7", "80μs"]
    assert tokenize("ŻÓŁĆ Straße cafe\u0301") == ["żółć", "strasse", "café"]
    assert tokenize("cafe") != tokenize("café")


def test_query_limits_are_explicit():
    assert query_terms("WAL WAL wal") == ["wal"]
    with pytest.raises(ValueError, match="4096"):
        query_terms("x" * 4097)
    with pytest.raises(ValueError, match="128"):
        query_terms(" ".join(str(i) for i in range(129)))
    assert match_expression(['" OR * - foo:bar']) == '"t22204f52202a202d20666f6f3a626172"'


def test_empty_oov_and_no_zero_padding(index):
    index.rebuild([record("b", "wal checkpoint"), record("a", "sensor clock")])
    assert not index.search("totallyunknownvocabulary", 50)
    assert not index.search("", 20)
    assert not index.search("!()*", 20)
    assert not index.search("wal", 0)
    assert ids(index, "checkpoint", 50) == ["b"]
    with pytest.raises(ValueError, match="K"):
        index.search("wal", -1)


def test_fts_operators_are_literal_terms_and_punctuation_cannot_execute(index):
    index.rebuild([record("a", "alpha"), record("b", "beta"), record("op", "OR NEAR tokens")])
    assert ids(index, '"alpha" NOT beta') == ids(index, "alpha beta")
    assert set(ids(index, "OR")) == {"op"}
    assert ids(index, "alpha:* - beta") == ids(index, "alpha beta")
    assert index.search('" NEAR(alpha,beta) ); DROP TABLE docs; --', 20)
    assert len(index.records()) == 3


def test_identifier_and_accent_distinctions_are_intentional(index):
    index.rebuild([record("id", "sample_rate"), record("accent", "café ŻÓŁĆ"), record("plain", "cafe"), record("code", "C++")])
    assert ids(index, "sample_rate") == ["id"]
    assert not ids(index, "sample")
    assert ids(index, "cafe\u0301") == ["accent"]
    assert ids(index, "cafe") == ["plain"]
    assert ids(index, "żółć") == ["accent"]
    assert ids(index, "C#") == ["code"]  # punctuation collision is documented, not hidden


def test_ties_are_stable_by_chunk_id_and_input_is_not_mutated(index):
    pool = [record("z", "identical sentence", section_path=["Root", "Evidence"]), record("a", "identical sentence")]
    before = deepcopy(pool)
    index.rebuild(pool)
    assert ids(index, "identical") == ["a", "z"]
    hit = index.search("identical", 2)[1]
    hit.record["metadata"]["section_path"].append("changed")
    assert index.search("identical", 2)[1].record["metadata"]["section_path"] == ["Root", "Evidence"]
    assert pool == before


def test_native_mutation_or_snapshot_rebuild_matches_clean_rebuild(index, tmp_path):
    pool = [record("a", "oldcalibration prerequisite", section_header="Old"), record("b", "remove obsolete"), record("keep", "stable checksum")]
    index.rebuild(pool)
    changed = record("a", "newvocabulary acceptance", path="current.md", section_header="Current")
    addition = record("added", "newvocabulary second document", path="second.md")
    index.mutate(upserts=[changed, addition], deletes=["b"])
    assert not ids(index, "oldcalibration")
    assert not ids(index, "obsolete")
    assert set(ids(index, "newvocabulary")) == {"a", "added"}
    assert next(h.record for h in index.search("newvocabulary", 20) if h.record["id"] == "a") == changed
    clean = type(index)(tmp_path / "clean", index.binding)
    try:
        clean.rebuild([changed, addition, pool[2]])
        for q in ("newvocabulary", "stable checksum", "acceptance document"):
            actual, expected = index.search(q, 20), clean.search(q, 20)
            assert [h.record for h in actual] == [h.record for h in expected]
            assert [h.score for h in actual] == pytest.approx([h.score for h in expected])
    finally:
        clean.close()
    index.close()
    reopened = type(index)(index.path, index.binding)
    try:
        assert set(ids(reopened, "newvocabulary")) == {"a", "added"}
        assert not ids(reopened, "obsolete")
    finally:
        reopened.close()


def test_bindings_and_invalid_scope_mutations_fail_closed(index):
    index.rebuild([record("a", "keep current")])
    with pytest.raises(ValueError, match="scope"):
        index.mutate(upserts=[record("p", "project secret", source="project")], deletes=["a"])
    assert ids(index, "current") == ["a"]
    with pytest.raises(ValueError, match="Duplicate"):
        index.rebuild([record("x", "x"), record("x", "changed")])
    with pytest.raises(ValueError, match="binding"):
        type(index)(index.path, Binding("another-corpus", "global"))


@pytest.mark.parametrize("backend", BACKENDS)
def test_project_partition_binding_prevents_cross_project_reload(backend, tmp_path):
    index = backend(tmp_path / "project", Binding("fixture", "project", "project-one"))
    try:
        index.rebuild([record("same-id", "private project note", source="project")])
    finally:
        index.close()
    with pytest.raises(ValueError, match="binding"):
        backend(tmp_path / "project", Binding("fixture", "project", "project-two"))


def test_fts_failure_rolls_back_both_content_and_postings(tmp_path):
    index = FTS5Index(tmp_path / "fts.db", Binding("test", "global"))
    try:
        index.rebuild([record("a", "keep old")])
        index.db.execute("""CREATE TRIGGER simulate_failure BEFORE INSERT ON docs
                          WHEN new.chunk_id='bad' BEGIN SELECT RAISE(ABORT,'injected'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            index.mutate(upserts=[record("bad", "new")], deletes=["a"])
        assert ids(index, "old") == ["a"]
        assert not ids(index, "new")
    finally:
        index.close()


def test_fts_refuses_an_unrelated_sqlite_database(tmp_path):
    path = tmp_path / "unrelated.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE unrelated(data TEXT)")
    db.close()
    before = path.read_bytes()
    with pytest.raises(ValueError, match="non-experimental"):
        FTS5Index(path, Binding("test", "global"))
    assert path.read_bytes() == before


@pytest.mark.skipif(importlib.util.find_spec("bm25s") is None, reason="Optional pinned BM25S dependency")
def test_failed_snapshot_publication_preserves_previous_generation(tmp_path, monkeypatch):
    index = BM25SIndex(tmp_path / "bm", Binding("test", "global"))
    index.rebuild([record("a", "old evidence")])
    before = (index.path / "CURRENT.json").read_bytes()
    def fail(*args):
        raise OSError("publication failed")
    monkeypatch.setattr("laew.rag.lexical_experiment.os.replace", fail)
    with pytest.raises(OSError, match="publication failed"):
        index.mutate(upserts=[record("b", "new evidence")])
    assert (index.path / "CURRENT.json").read_bytes() == before
    assert ids(index, "old") == ["a"]
    index.close()


def test_all_tokenless_snapshot_can_reload(index):
    index.rebuild([record("punctuation", "*** !")])
    index.close()
    reopened = type(index)(index.path, index.binding)
    try:
        assert not reopened.search("word", 20)
        assert len(reopened.records()) == 1
    finally:
        reopened.close()
