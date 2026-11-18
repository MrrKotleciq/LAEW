"""Evaluation-only fixed-body citation formats. No runtime caller or selection.

The caller supplies immutable, manifest-verified source and passage bindings.
This module has no retrieval, embedding, model, rubric or filesystem interface.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import DocumentChunk

VERSION = 'fixed-body-citations-v1'
VARIANTS = ('S0', 'S1', 'S2', 'S3')
SEPARATOR = '\n\n---\n\n'
VERBOSE_SEPARATOR = '\n\n[Independent passage; intervening source or procedure steps may be omitted]\n\n'
NOTICE = 'Independent source passages, not consecutive procedure steps. Offsets: Unicode code points in LF snapshots. Frozen payload annotations remain annotations.\n'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


@dataclass(frozen=True)
class Source:
    source_id: str
    revision: str
    sha256: str
    text: str
    path: str
    applicability: str
    scope: str = 'global'

    def __post_init__(self):
        if (not all(isinstance(v, str) and v for v in (self.source_id, self.revision, self.path, self.applicability))
                or self.scope not in ('global', 'project') or '\r' in self.text
                or not valid_hash(self.sha256) or digest(self.text) != self.sha256):
            raise ValueError('Invalid immutable source identity/revision/LF snapshot')

    @property
    def key(self):
        return digest(canonical([self.scope, self.source_id, self.revision, self.sha256, self.path, self.applicability]))


@dataclass(frozen=True)
class Passage:
    chunk_id: str
    source_key: str
    body: str
    body_sha256: str
    ranges: tuple[tuple[int, int], ...]
    metadata_json: str
    mapping_sha256: str
    annotations: bool = False
    clipped: bool = False
    restricted: tuple[str, ...] = ()

    @property
    def binding(self):
        return digest(canonical(dict(id=self.chunk_id, source=self.source_key,
            body_sha256=self.body_sha256, ranges=self.ranges, metadata=self.metadata_json,
            mapping_sha256=self.mapping_sha256, annotations=self.annotations,
            clipped=self.clipped, restricted=self.restricted)))


@dataclass(frozen=True)
class FixedContext:
    sources: tuple[Source, ...]
    passages: tuple[Passage, ...]
    approved_bindings: tuple[str, ...]
    contract_sha256: str
    historical_context: str


@dataclass(frozen=True)
class Encoded:
    variant: str
    context: str
    # start/end are positions in serialized Unicode text, not source offsets.
    body_positions: tuple[tuple[int, int], ...]
    source_aliases: tuple[tuple[str, str], ...]
    repeated_source_header_chars: int = 0

    @property
    def tokens(self):
        return (len(self.context) + 3) // 4


def validate(frame):
    if not valid_hash(frame.contract_sha256):
        raise ValueError('Missing pinned fixed-body contract')
    sources = {s.key: s for s in frame.sources}
    if len(sources) != len(frame.sources):
        raise ValueError('Duplicate source binding')
    if len({s.scope for s in frame.sources}) > 1:
        raise ValueError('A fixed context cannot cross source scopes')
    if len({p.chunk_id for p in frame.passages}) != len(frame.passages):
        raise ValueError('Duplicate selected fragment identity')
    if tuple(p.binding for p in frame.passages) != frame.approved_bindings:
        raise ValueError('Selected order/body/source/range/metadata binding changed')
    if set(sources) != {p.source_key for p in frame.passages}:
        raise ValueError('Missing or unused source binding')
    for p in frame.passages:
        if (p.source_key not in sources or not p.chunk_id or not p.body or '\r' in p.body
                or digest(p.body) != p.body_sha256 or not valid_hash(p.mapping_sha256)
                or not p.ranges or type(p.annotations) is not bool or type(p.clipped) is not bool
                or not isinstance(p.restricted, tuple) or any(not isinstance(r, str) or not r for r in p.restricted)):
            raise ValueError('Invalid payload/mapping/source offsets')
        previous = -1
        for pair in p.ranges:
            if (not isinstance(pair, tuple) or len(pair) != 2
                    or any(type(n) is not int for n in pair)):
                raise ValueError('Source offsets must be integer Unicode pairs')
            a, z = pair
            if not 0 <= a < z <= len(sources[p.source_key].text) or a < previous:
                raise ValueError('Invalid or noncanonical source offsets')
            previous = z
        meta = json.loads(p.metadata_json)
        if canonical(meta) != p.metadata_json or not isinstance(meta, dict):
            raise ValueError('Metadata binding is not canonical')
        if meta.get('frontmatter') is not None and not isinstance(meta['frontmatter'], dict):
            raise ValueError('Invalid document applicability metadata')
        path = meta.get('section_path')
        if path is not None and (not isinstance(path, list) or any(not isinstance(v, str) for v in path)):
            raise ValueError('Invalid section applicability')
        if p.clipped and len(frame.passages) != 1:
            raise ValueError('Historical clipping only applies to the first sole passage')
    return sources


def _legacy(frame, sources, variant):
    if variant == 'S1' and len({s.path for s in sources.values()}) != len(sources):
        raise ValueError('Compact historical labels cannot disambiguate same-path revisions')
    renderer = RAGPipeline(None, None, max_context_tokens=1_000_000)
    parts, positions, offset = [], [], 0
    for p in frame.passages:
        s = sources[p.source_key]
        meta = json.loads(p.metadata_json)
        if variant == 'S1':
            meta.pop('tags', None)
            meta.pop('backlinks', None)
        chunk = DocumentChunk(p.chunk_id, p.body, source=s.scope, file_path=s.path, metadata=meta)
        part, used, _ = renderer._build_context([(chunk, 1.0)])
        if len(used) != 1 or used[0][0].text != p.body:
            raise ValueError('Serializer unexpectedly clipped a fixed body')
        prefix = len(part) - len(p.body)
        if parts:
            offset += len(SEPARATOR)
        positions.append((offset + prefix, offset + prefix + len(p.body)))
        part += '...' if p.clipped else ''
        parts.append(part)
        offset += len(part)
    context = SEPARATOR.join(parts)
    if variant == 'S0' and context != frame.historical_context:
        raise ValueError('Historical baseline is not byte-identical')
    return Encoded(variant, context, tuple(positions), ())


def _grouped(frame, sources, variant):
    if not frame.passages:
        return Encoded(variant, '', (), ())
    aliases, sections, registry = {}, {}, {}
    for p in frame.passages:
        s = sources[p.source_key]
        meta = json.loads(p.metadata_json)
        section = dict(path=meta.get('section_path'), header=meta.get('section_header'))
        section_key = canonical(section)
        if s.key not in aliases:
            alias = 'D' + str(len(aliases) + 1)
            aliases[s.key] = alias
            sections[s.key] = {}
            registry[alias] = dict(id=s.source_id, revision=s.revision, sha256=s.sha256,
                path=s.path, scope=s.scope, applies=s.applicability, sections={}, metadata={})
        item = registry[aliases[s.key]]
        docmeta = {k: (meta.get('frontmatter') or {}).get(k) for k in ('type', 'status')}
        if item['metadata'] and item['metadata'] != docmeta:
            raise ValueError('Conflicting document metadata for the same source binding')
        item['metadata'] = docmeta
        if section_key not in sections[s.key]:
            h = 'H' + str(len(sections[s.key]) + 1)
            sections[s.key][section_key] = h
            item['sections'][h] = section
    context = NOTICE + 'Contract: ' + frame.contract_sha256 + '\nSources: ' + canonical(registry) + '\n'
    positions, repeat_headers = [], 0
    separator = VERBOSE_SEPARATOR if variant == 'S2' else SEPARATOR
    for i, p in enumerate(frame.passages, 1):
        meta = json.loads(p.metadata_json)
        section_key = canonical(dict(path=meta.get('section_path'), header=meta.get('section_header')))
        alias = aliases[p.source_key]
        header = dict(s=alias, h=sections[p.source_key][section_key], r=p.ranges, n=len(p.body))
        if p.annotations:
            header['annotations'] = True
        if p.clipped:
            header['clipped'] = True
        if p.restricted:
            header['restricted'] = p.restricted
        if i > 1:
            context += separator
        context += '@@P' + str(i) + ' ' + canonical(header) + '\n'
        positions.append((len(context), len(context) + len(p.body)))
        context += p.body + ('...' if p.clipped else '') + '\n@@ENDP' + str(i) + '\n'
        repeat_headers += len(canonical(registry[alias]))
    # Arithmetic control, not an additional experimental format: repeated
    # identical registry descriptions versus their once-per-source representation.
    repeat_headers -= sum(len(canonical(v)) for v in registry.values())
    return Encoded(variant, context, tuple(positions), tuple(aliases.items()), repeat_headers)


def serialize(frame, variant):
    if variant not in VARIANTS:
        raise ValueError('Only predeclared S0–S3 are permitted')
    sources = validate(frame)
    encoded = _legacy(frame, sources, variant) if variant in ('S0', 'S1') else _grouped(frame, sources, variant)
    if len(encoded.body_positions) != len(frame.passages):
        raise ValueError('One-to-one passage mapping failed')
    for p, (a, z) in zip(frame.passages, encoded.body_positions):
        if encoded.context[a:z] != p.body:
            raise ValueError('Source-body character changed')
    return encoded


def decode_grouped(frame, encoded):
    """Length-framed validation handles marker-looking text INSIDE a body."""
    expected = serialize(frame, encoded.variant)
    if encoded.variant not in ('S2', 'S3') or encoded.context != expected.context:
        raise ValueError('Unknown reference, ownership, range or framing change')
    if not frame.passages:
        return []
    text = encoded.context
    prefix = NOTICE + 'Contract: ' + frame.contract_sha256 + '\nSources: '
    if not text.startswith(prefix):
        raise ValueError('Missing provenance registry')
    end = text.index('\n', len(prefix))
    registry = json.loads(text[len(prefix):end])
    pos = end + 1
    recovered = []
    separator = VERBOSE_SEPARATOR if encoded.variant == 'S2' else SEPARATOR
    for i, p in enumerate(frame.passages, 1):
        if i > 1:
            if text[pos:pos+len(separator)] != separator:
                raise ValueError('Missing independent-passage boundary')
            pos += len(separator)
        start = '@@P' + str(i) + ' '
        if not text.startswith(start, pos):
            raise ValueError('Invalid passage identity/order')
        line_end = text.index('\n', pos)
        header = json.loads(text[pos+len(start):line_end])
        if header['s'] not in registry:
            raise ValueError('Unresolved compact source reference')
        a = line_end + 1
        z = a + header['n']
        body = text[a:z]
        tail = ('...' if p.clipped else '') + '\n@@ENDP' + str(i) + '\n'
        if text[z:z+len(tail)] != tail:
            raise ValueError('Invalid body length or closing boundary')
        recovered.append((p.chunk_id, body, header['r'], registry[header['s']]))
        pos = z + len(tail)
    if pos != len(text):
        raise ValueError('Unassigned text after final passage')
    return recovered
