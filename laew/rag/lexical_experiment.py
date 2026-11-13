"""Isolated lexical backend adapters. Never imported by production RAG.

Each index is bound to one authorized corpus/scope/project. Authorization and
freshness must be established by the caller; this is not a new security boundary.
No embeddings, inference, language-specific processing or fusion is performed.
"""
from dataclasses import asdict, dataclass
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sqlite3
import unicodedata
import uuid

TOKENIZER = "nfkc-casefold-unicode-word-v1"


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())


def query_terms(text: str) -> list[str]:
    if len(text) > 4096:
        raise ValueError("Query exceeds 4096 characters")
    terms = list(dict.fromkeys(tokenize(text)))
    if len(terms) > 128:
        raise ValueError("Query exceeds 128 distinct terms")
    return terms


def encoded(term: str) -> str:
    # ASCII tokens make FTS5 tokenization identical to BM25S's supplied tokens,
    # including underscores, casefold expansions and preserved diacritics.
    return "t" + term.encode("utf-8").hex()


def match_expression(terms: list[str]) -> str:
    return " OR ".join('"' + encoded(term) + '"' for term in terms)


@dataclass(frozen=True)
class Binding:
    corpus: str
    scope: str
    project: str | None = None

    def __post_init__(self):
        if not self.corpus or self.scope not in ("global", "project"):
            raise ValueError("A corpus and single scope are required")
        if (self.scope == "project" and not self.project) or (self.scope == "global" and self.project is not None):
            raise ValueError("Project identity must exist exactly for project scope")

    def data(self):
        return asdict(self) | {"tokenizer": TOKENIZER, "format": "lexical-experiment-v1"}


def validate_records(records, binding):
    records = list(records)
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("Duplicate chunk ID")
    for r in records:
        if r["source"] != binding.scope:
            raise ValueError("Record escaped bound scope")
        if not r["id"] or not isinstance(r["text"], str):
            raise ValueError("Invalid chunk record")
    # Embeddings are deliberately excluded from lexical storage and memory.
    return [deepcopy({k: r[k] for k in ("id", "text", "source", "path", "metadata")}) for r in records]


@dataclass(frozen=True)
class Hit:
    record: dict
    score: float


def validate_k(k):
    if not isinstance(k, int) or k < 0:
        raise ValueError("K must be a nonnegative integer")


class FTS5Index:
    """Transactional native add/update/delete; one SQLite database per binding."""
    score_order = "ascending (native negative bm25)"

    def __init__(self, path, binding):
        self.path, self.binding = Path(path), binding
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        try:
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables:
                if "binding" not in tables:
                    raise ValueError("Refusing to open a non-experimental SQLite database")
                stored = self.db.execute("SELECT value FROM binding WHERE key='identity'").fetchone()
                if not stored or json.loads(stored[0]) != binding.data():
                    raise ValueError("Index binding mismatch")
            else:
                self.db.executescript("""
                    CREATE TABLE binding(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE docs(chunk_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, tokens TEXT NOT NULL);
                    CREATE VIRTUAL TABLE lexical USING fts5(tokens, content='docs', content_rowid='rowid', tokenize='ascii');
                    CREATE TRIGGER docs_insert AFTER INSERT ON docs BEGIN
                        INSERT INTO lexical(rowid,tokens) VALUES(new.rowid,new.tokens);
                    END;
                    CREATE TRIGGER docs_delete AFTER DELETE ON docs BEGIN
                        INSERT INTO lexical(lexical,rowid,tokens) VALUES('delete',old.rowid,old.tokens);
                    END;
                    CREATE TRIGGER docs_update AFTER UPDATE ON docs BEGIN
                        INSERT INTO lexical(lexical,rowid,tokens) VALUES('delete',old.rowid,old.tokens);
                        INSERT INTO lexical(rowid,tokens) VALUES(new.rowid,new.tokens);
                    END;
                """)
                with self.db:
                    self.db.execute("INSERT INTO binding VALUES('identity',?)", (json.dumps(binding.data(), sort_keys=True),))
            self.db.execute("PRAGMA cache_size=-2048")
        except Exception:
            self.db.close()
            raise

    def rebuild(self, records):
        records = validate_records(records, self.binding)
        with self.db:
            self.db.execute("DELETE FROM docs")
            self._upsert(records)
            self._generation()

    def _generation(self):
        self.db.execute("INSERT OR REPLACE INTO binding VALUES('generation',?)", (uuid.uuid4().hex,))

    def _upsert(self, records):
        self.db.executemany("""INSERT INTO docs(chunk_id,payload,tokens) VALUES(?,?,?)
            ON CONFLICT(chunk_id) DO UPDATE SET payload=excluded.payload,tokens=excluded.tokens""",
            [(r["id"], json.dumps(r, ensure_ascii=False), " ".join(encoded(t) for t in tokenize(r["text"]))) for r in records])

    def mutate(self, upserts=(), deletes=()):
        records = validate_records(upserts, self.binding)
        deletes = list(deletes)
        if {r["id"] for r in records}.intersection(deletes):
            raise ValueError("An ID cannot be updated and deleted in one mutation")
        with self.db:
            self.db.executemany("DELETE FROM docs WHERE chunk_id=?", [(i,) for i in deletes])
            self._upsert(records)
            self._generation()

    def search(self, query, k):
        validate_k(k)
        terms = query_terms(query)
        if not k or not terms:
            return []
        rows = self.db.execute("""SELECT docs.payload,bm25(lexical) AS score
            FROM lexical JOIN docs ON docs.rowid=lexical.rowid WHERE lexical MATCH ?
            ORDER BY score ASC,docs.chunk_id ASC LIMIT ?""", (match_expression(terms), k))
        return [Hit(json.loads(payload), float(score)) for payload, score in rows]

    def records(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM docs ORDER BY chunk_id")]

    def close(self):
        self.db.close()


class BM25SIndex:
    """Eager-score snapshots; mutation explicitly rebuilds the whole bound corpus.

    New generations are saved before publishing CURRENT.json with os.replace.
    Existing generations are retained; garbage collection/concurrent writers and
    coordination with Chroma generations are intentionally outside this experiment.
    """
    score_order = "descending (positive Lucene BM25)"

    def __init__(self, path, binding, *, mmap=True):
        import bm25s
        if bm25s.__version__ != "0.3.15":
            raise ValueError("This experiment pins bm25s==0.3.15")
        self.path, self.binding = Path(path), binding
        self.model, self._records = None, []
        identity_path = self.path / "binding.json"
        if self.path.exists() and any(self.path.iterdir()):
            if not identity_path.exists() or json.loads(identity_path.read_text(encoding="utf-8")) != binding.data():
                raise ValueError("Index binding mismatch or non-experimental directory")
        else:
            self.path.mkdir(parents=True, exist_ok=True)
            identity_path.write_text(json.dumps(binding.data()), encoding="utf-8")
        pointer = self.path / "CURRENT.json"
        if pointer.exists():
            state = json.loads(pointer.read_text(encoding="utf-8"))
            generation = state["generation"]
            if not re.fullmatch(r"[0-9a-f]{32}", generation):
                raise ValueError("Invalid snapshot generation")
            snapshot = self.path / generation
            self._records = validate_records(json.loads((snapshot / "records.json").read_text(encoding="utf-8")), binding)
            if state["has_scores"]:
                self.model = bm25s.BM25.load(snapshot, mmap=mmap, allow_pickle=False, show_progress=False, verbosity=0)

    def rebuild(self, records):
        import bm25s
        records = sorted(validate_records(records, self.binding), key=lambda r: r["id"])
        model = None
        if records:
            # A tokenless corpus is represented explicitly; avoid BM25S's
            # undefined average-length calculation for entirely empty content.
            corpus_tokens = [tokenize(r["text"]) for r in records]
            if any(corpus_tokens):
                model = bm25s.BM25(k1=1.2, b=.75, method="lucene", backend="numpy", auto_compile=False)
                model.index(corpus_tokens, show_progress=False)
        generation = uuid.uuid4().hex
        snapshot = self.path / generation
        snapshot.mkdir()
        (snapshot / "records.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        if model is not None:
            model.save(snapshot, allow_pickle=False, show_progress=False)
        pointer = self.path / "CURRENT.next.json"
        pointer.write_text(json.dumps({"generation": generation, "has_scores": model is not None}), encoding="utf-8")
        os.replace(pointer, self.path / "CURRENT.json")
        self.close()
        self.model, self._records = model, records

    def mutate(self, upserts=(), deletes=()):
        records = validate_records(upserts, self.binding)
        deletes = set(deletes)
        if {r["id"] for r in records}.intersection(deletes):
            raise ValueError("An ID cannot be updated and deleted in one mutation")
        merged = {r["id"]: r for r in self._records if r["id"] not in deletes}
        merged.update({r["id"]: r for r in records})
        self.rebuild(list(merged.values()))

    def search(self, query, k):
        import numpy as np
        validate_k(k)
        terms = query_terms(query)
        if not k or not terms or self.model is None:
            return []
        scores = self.model.get_scores(terms)
        positive = np.flatnonzero(scores > 0)
        if not len(positive):
            return []
        # Full stable sorting of positive matches: simple and deterministic.
        # This O(M log M) step is measured, not confused with BM25S score latency.
        ordered = positive[np.argsort(-scores[positive], kind="stable")][:k]
        return [Hit(deepcopy(self._records[int(i)]), float(scores[i])) for i in ordered]

    def records(self):
        return deepcopy(self._records)

    def close(self):
        if self.model is not None:
            for array in self.model.scores.values():
                mapping = getattr(array, "_mmap", None)
                if mapping is not None:
                    mapping.close()
        self.model = None
