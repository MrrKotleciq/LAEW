"""Isolated seed-guided Chroma retrieval. Not imported by production RAG.

The caller owns authorization and a generation-bound snapshot. A mandatory lease
must hold existing synchronization locks across ALL reads and validation. This
module never embeds, writes, opens a database, or retries without source filters.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
from typing import Callable, ContextManager

from laew.rag.pipeline import fragment_key
from laew.rag.vector_store import DocumentChunk, _decode_metadata_value

DEPTH = FINAL_LIMIT = 10
DOCUMENT_BEAM = 3
FOLLOWUP_DEPTH = 128
RESPONSE_BYTES = 1024 * 1024


class UnsafeEvidence(RuntimeError):
    """Authorization, identity, payload, or freshness failure: never fall back."""


class FilterUnavailable(RuntimeError):
    """Explicit availability failure: fresh dense seeds may be returned."""


def document_path(path):
    p = PureWindowsPath(path)
    if not path or p.root or p.drive or '..' in p.parts or ':' in path:
        raise UnsafeEvidence('Document path must be a safe logical relative path')
    return p.as_posix().casefold()


def payload(chunk):
    return {'id': chunk.chunk_id, 'text': chunk.text, 'source': chunk.source,
            'path': chunk.file_path, 'metadata': chunk.metadata}


def signature(chunk):
    return hashlib.sha256(json.dumps(payload(chunk), ensure_ascii=False, sort_keys=True,
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Binding:
    collection_id: str
    scope: str
    project_root: str | None = None

    def __post_init__(self):
        if self.scope not in ('global', 'project') or not self.collection_id:
            raise UnsafeEvidence('Invalid scope binding')
        if (self.scope == 'project') != bool(self.project_root):
            raise UnsafeEvidence('Project identity required only for project scope')
        if self.project_root and not Path(self.project_root).is_absolute():
            raise UnsafeEvidence('Project root must be absolute')


@dataclass(frozen=True)
class Snapshot:
    binding: Binding
    generation: str
    signatures: dict[str, str]
    # Mapping is separate so an absent structural mapping can safely degrade.
    documents: dict[str, str]
    spellings: dict[str, tuple[str, ...]]
    counts: dict[str, int]

    @classmethod
    def build(cls, binding, generation, chunks):
        if not generation:
            raise UnsafeEvidence('Missing generation')
        signatures, documents, spellings, counts = {}, {}, {}, {}
        for chunk in chunks:
            if chunk.source != binding.scope or chunk.chunk_id in signatures:
                raise UnsafeEvidence('Duplicate ID or source outside authorized snapshot')
            doc = document_path(chunk.file_path)
            signatures[chunk.chunk_id] = signature(chunk)
            documents[chunk.chunk_id] = doc
            spellings.setdefault(doc, set()).add(chunk.file_path)
            counts[doc] = counts.get(doc, 0) + 1
        return cls(binding, generation, signatures, documents,
                   {k: tuple(sorted(v)) for k, v in spellings.items()}, counts)


@contextmanager
def kb_lease(kb, snapshot):
    """Optional experimental bridge to existing locks; no production caller.

    Snapshot must have been built under the same generation and collection.
    A freshness failure is an error, never a dense fallback.
    """
    from laew.rag.sync import acquire_fresh_scopes, sync_status
    scope = snapshot.binding.scope
    if scope == 'project' and Path(kb.project_root).resolve() != Path(snapshot.binding.project_root).resolve():
        raise UnsafeEvidence('Project binding mismatch')
    locks, error = acquire_fresh_scopes(kb, (scope,))
    if error:
        raise UnsafeEvidence(error)
    def check():
        status = sync_status(kb, scope)
        store = kb.global_store if scope == 'global' else kb.project_store
        if (status['state'] != 'successfully synchronized' or
                status['generation'] != snapshot.generation or
                str(store._collection.id) != snapshot.binding.collection_id):
            raise UnsafeEvidence('Freshness/generation/collection changed')
    try:
        check()
        yield check
        check()
    finally:
        for lock in reversed(locks):
            lock.release()


@dataclass
class Retrieval:
    pairs: list[tuple[DocumentChunk, float]]
    seeds: list[tuple[DocumentChunk, float]]
    diagnostics: dict = field(default_factory=dict)


class ChromaDrillDown:
    def __init__(self, collection, snapshot: Snapshot,
                 lease: Callable[[], ContextManager[Callable[[], None]]]):
        if str(collection.id) != snapshot.binding.collection_id:
            raise UnsafeEvidence('Collection binding mismatch')
        self.collection, self.snapshot, self.lease = collection, snapshot, lease

    def _query(self, vector, paths, limit, counters):
        scope = self.snapshot.binding.scope
        where = {'source': scope}
        if paths is not None:
            where = {'$and': [where, {'file_path': {'$in': list(paths)}}]}
        counters['chroma_calls'] += 1
        from chromadb.errors import InternalError
        try:
            result = self.collection.query(query_embeddings=[vector], n_results=limit,
                                           where=where, include=['metadatas', 'distances'])
        except InternalError as error:
            if paths is not None:
                raise FilterUnavailable('Chroma internal availability failure') from error
            raise
        ids, metas, distances = (result[key][0] for key in ('ids', 'metadatas', 'distances'))
        if len(ids) > limit or not len(ids) == len(metas) == len(distances):
            raise UnsafeEvidence('Malformed or oversized result')
        size = len(json.dumps([ids, metas, distances], ensure_ascii=False, allow_nan=False).encode())
        counters['fetched_metadata_bytes'] += size
        counters['fetched_records'] += len(ids)
        if size > RESPONSE_BYTES:
            raise UnsafeEvidence('Response exceeds memory consumption bound')
        pairs, seen = [], set()
        for id_, meta, distance in zip(ids, metas, distances):
            if not isinstance(meta, dict) or id_ not in self.snapshot.signatures:
                raise UnsafeEvidence('Unknown ID or missing metadata')
            chunk = DocumentChunk(id_, meta.get('text', ''), source=meta.get('source'),
                                  file_path=meta.get('file_path', ''), metadata={
                                      k: _decode_metadata_value(v) for k, v in meta.items()
                                      if k not in ('text', 'source', 'file_path')})
            if (chunk.source != scope or signature(chunk) != self.snapshot.signatures[id_] or
                    (paths is not None and chunk.file_path not in paths)):
                raise UnsafeEvidence('Scope, document filter or current payload mismatch')
            score = 1.0 - float(distance)
            if not math.isfinite(score) or not -1.000001 <= score <= 1.000001:
                raise UnsafeEvidence('Invalid cosine')
            if id_ not in seen and score >= .3 and chunk.text:
                pairs.append((chunk, score))
                seen.add(id_)
        pairs.sort(key=lambda p: (-p[1], p[0].chunk_id))
        # Same source fragment identity as the current pipeline, not text-only
        # dedup across distinct documents with different provenance.
        unique, fragments = [], set()
        for pair in pairs:
            key = fragment_key(pair[0])
            if key not in fragments:
                unique.append(pair)
                fragments.add(key)
        return unique

    def retrieve(self, vector, *, hierarchical=False):
        vector = [float(x) for x in vector]
        norm = math.sqrt(sum(x*x for x in vector))
        if not vector or not math.isfinite(norm) or norm == 0:
            raise ValueError('Invalid original query embedding')
        vector = [x / norm for x in vector]
        counters = {'chroma_calls': 0, 'fetched_metadata_bytes': 0, 'fetched_records': 0,
                    'fallback': None, 'routed_documents': [], 'excluded_seed_documents': [],
                    'seed_depth': DEPTH, 'followup_depth': FOLLOWUP_DEPTH, 'final_limit': FINAL_LIMIT}
        with self.lease() as check:
            check()
            if str(self.collection.id) != self.snapshot.binding.collection_id:
                raise UnsafeEvidence('Collection changed during lease')
            count = len(self.snapshot.signatures)
            seeds = self._query(vector, None, min(DEPTH, count), counters)[:DEPTH] if count else []
            check()
            pairs = seeds
            if hierarchical and seeds:
                try:
                    docs = []
                    for chunk, _ in seeds:
                        doc = self.snapshot.documents.get(chunk.chunk_id)
                        if doc is None:
                            raise FilterUnavailable('missing_document_mapping')
                        if doc != document_path(chunk.file_path):
                            raise UnsafeEvidence('Conflicting document mapping')
                        if doc not in docs:
                            docs.append(doc)
                    selected = docs[:DOCUMENT_BEAM]
                    counters.update(routed_documents=selected, excluded_seed_documents=docs[DOCUMENT_BEAM:])
                    if any(not self.snapshot.spellings.get(d) or not self.snapshot.counts.get(d) for d in selected):
                        raise FilterUnavailable('missing_document_mapping')
                    paths = tuple(p for d in selected for p in self.snapshot.spellings[d])
                    child_count = sum(self.snapshot.counts[d] for d in selected)
                    pairs = self._query(vector, paths, min(FOLLOWUP_DEPTH, child_count), counters)[:FINAL_LIMIT]
                except (FilterUnavailable, OSError, ConnectionError, NotImplementedError) as error:
                    check()
                    pairs = seeds
                    counters['fallback'] = f'{type(error).__name__}: {error}'
            check()
            counters['returned'] = len(pairs)
            return Retrieval(pairs, seeds, counters)
