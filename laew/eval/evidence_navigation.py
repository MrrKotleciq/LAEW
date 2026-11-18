"""Offline, bounded navigation of explicitly supplied immutable source files.

Offsets are zero-based Unicode code points and ranges are half-open. Results and
final packets are JSON-compatible dictionaries; token accounting uses canonical
JSON character counts, rounded up independently for every response.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _tokens(value):
    return (len(_json(value)) + 3) // 4


@dataclass(frozen=True)
class Source:
    id: str
    owner: str
    revision: str
    sha256: str
    path: str | Path
    applicability: str
    restricted_ranges: tuple[tuple[int, int], ...] = ()


class NavigationSession:
    def __init__(self, sources, allowed_ids, initial_packets=(), budget_tokens=4000,
                 packet_tokens=1000, max_ops=3):
        sources = list(sources)
        self.sources = {s.id: s for s in sources}
        if len(self.sources) != len(sources) or not set(allowed_ids) <= self.sources.keys():
            raise ValueError('invalid source allowlist')
        self.allowed = frozenset(allowed_ids)
        if any(not isinstance(n, int) or isinstance(n, bool) or n < 0
               for n in (budget_tokens, packet_tokens, max_ops)):
            raise ValueError('invalid budget')
        self.budget_tokens, self.packet_tokens, self.max_ops = budget_tokens, packet_tokens, max_ops
        self.used_tokens = self.operations = self.final_tokens = 0
        self.inspected = []
        self.transcript = []
        self.finished = False
        for packet in initial_packets:
            sid, start, end = packet['source_id'], packet['start'], packet['end']
            text = self._load(sid)
            self._validate_range(text, start, end)
            if self._visible(sid, start, end) != [(start, end)]:
                raise ValueError('initial packet overlaps restricted range')
            item = {'kind': 'initial', 'source': self._metadata(sid), 'segments': [self._segment(text, start, end)]}
            if _tokens(item) > self.packet_tokens or self.used_tokens + _tokens(item) > self.budget_tokens:
                raise ValueError('initial packet exceeds budget')
            self.used_tokens += _tokens(item)
            self.inspected.append((sid, start, end))
            self.transcript.append(item)

    def _load(self, sid):
        if sid not in self.allowed:
            raise ValueError('source not allowed')
        s = self.sources[sid]
        if s.owner != 'global' or not all(isinstance(x, str) and x for x in (s.id, s.revision, s.sha256, s.applicability)):
            raise ValueError('invalid source metadata')
        raw = Path(s.path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != s.sha256:
            raise ValueError('source hash mismatch')
        text = raw.decode('utf-8', errors='strict')
        if '\r' in text:
            raise ValueError('source must use LF line endings')
        last = 0
        for a, b in s.restricted_ranges:
            if not isinstance(a, int) or not isinstance(b, int) or a < last or b <= a or b > len(text):
                raise ValueError('invalid restricted ranges')
            last = b
        return text

    def _metadata(self, sid):
        s = self.sources[sid]
        return {'id': s.id, 'owner': s.owner, 'revision': s.revision,
                'sha256': s.sha256, 'applicability': s.applicability}

    @staticmethod
    def _validate_range(text, start, end):
        if (not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int)
                or isinstance(end, bool) or start < 0 or end <= start or end > len(text)):
            raise ValueError('invalid range')

    def _visible(self, sid, start, end):
        segments, cursor = [], start
        for a, b in self.sources[sid].restricted_ranges:
            if b <= cursor: continue
            if a >= end: break
            if cursor < a: segments.append ( (cursor, min(a, end)) )
            cursor = max(cursor, b)
            if cursor >= end: break
        if cursor < end: segments.append((cursor, end))
        return segments

    @staticmethod
    def _segment(text, start, end):
        return {'start': start, 'end': end, 'line_start': text.count('\n', 0, start) + 1,
                'line_end': text.count('\n', 0, end - 1) + 1, 'text': text[start:end]}

    def _begin(self):
        if self.finished or self.operations >= self.max_ops:
            raise ValueError('session closed or operation limit reached')
        self.operations += 1

    def _emit(self, result, candidates=(), max_chars=None):
        # Never truncate metadata or join disjoint spans. A partial span retains
        # its real offsets; its content is charged including all JSON provenance.
        limit = (self.budget_tokens - self.used_tokens) * 4
        if max_chars is not None:
            if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 0:
                raise ValueError('invalid response limit')
            limit = min(limit, max_chars)
        result['request_limit'] = max_chars
        result['segments'] = []
        result['omissions'] = []
        result.setdefault('more_results_omitted', False)
        requested = result.get('requested')
        if result.get('source'):
            sid = result['source']['id']
            if not requested: requested = [0, len(self._load(sid))]
            for a, b in self.sources[sid].restricted_ranges:
                a, b = max(a, requested[0]), min(b, requested[1])
                if a < b: result['omissions'].append({'start': a, 'end': b, 'reason': 'restricted'})
        if len(_json(result)) > limit:
            raise ValueError('insufficient response budget for provenance')
        newly_inspected = []
        for sid, text, start, end in candidates:
            lo, hi = 0, end - start
            while lo < hi:
                mid = (lo + hi + 1) // 2
                result['segments'].append(self._segment(text, start, start + mid))
                result['omissions'].append({'start': start + mid, 'end': end, 'reason': 'budget'})
                fits = len(_json(result)) <= limit
                result['omissions'].pop()
                result['segments'].pop()
                if fits: lo = mid
                else: hi = mid - 1
            if lo:
                result['segments'].append(self._segment(text, start, start + lo))
                newly_inspected.append((sid, start, start + lo))
            if lo < end - start:
                result['omissions'].append({'start': start + lo, 'end': end, 'reason': 'budget'})
                result['more_results_omitted'] = True
                break
        if len(_json(result)) > limit:
            raise ValueError('insufficient response budget for omissions')
        self.used_tokens += _tokens(result)
        self.inspected.extend(newly_inspected)
        self.transcript.append(result)
        return result

    def menu(self, max_chars=None):
        if self.finished: raise ValueError('session closed')
        entries = []
        omitted = False
        for sid in sorted(self.allowed):
            self._load(sid)
            entry = self._metadata(sid)
            trial = {'kind': 'menu', 'sources': entries + [entry], 'request_limit': max_chars, 'segments': [], 'omissions': [], 'more_results_omitted': False}
            limit = (self.budget_tokens - self.used_tokens) * 4
            if max_chars is not None: limit = min(limit, max_chars)
            if len(_json(trial)) > limit:
                omitted = True
                break
            entries.append(entry)
        return self._emit({'kind': 'menu', 'sources': entries, 'more_results_omitted': omitted}, max_chars=max_chars)

    def read(self, sid, start, end, max_chars=None):
        self._begin()
        return self._read(sid, start, end, max_chars)

    def _read(self, sid, start, end, max_chars):
        text = self._load(sid)
        self._validate_range(text, start, end)
        return self._emit({'kind': 'read', 'source': self._metadata(sid), 'requested': [start, end]},
                          [(sid, text, a, b) for a, b in self._visible(sid, start, end)], max_chars)

    def read_lines(self, sid, first_line, last_line, max_chars=None):
        """Read inclusive one-based line numbers, reporting codepoint ranges."""
        self._begin()
        text = self._load(sid)
        if (not isinstance(first_line, int) or isinstance(first_line, bool)
                or not isinstance(last_line, int) or isinstance(last_line, bool)
                or first_line < 1 or last_line < first_line):
            raise ValueError('invalid line range')
        lines = text.splitlines(keepends=True)
        if last_line > len(lines):
            raise ValueError('invalid line range')
        start = sum(map(len, lines[:first_line - 1]))
        end = sum(map(len, lines[:last_line]))
        return self._read(sid, start, end, max_chars)

    def grep(self, sid, query, max_chars=None):
        self._begin()
        text = self._load(sid)
        if not isinstance(query, str) or not query or '\n' in query or '\r' in query:
            raise ValueError('query must be a nonempty single-line literal')
        candidates = []
        for a, b in self._visible(sid, 0, len(text)):
            pos = a
            while True:
                match = re.search(re.escape(query), text[pos:b], re.IGNORECASE)
                if not match: break
                pos += match.start()
                line_start = max(a, text.rfind('\n', a, pos) + 1)
                newline = text.find('\n', pos, b)
                line_end = b if newline < 0 else newline + 1
                if not candidates or candidates[-1][2:] != (line_start, line_end):
                    candidates.append((sid, text, line_start, line_end))
                pos += max(1, match.end() - match.start())
        return self._emit({'kind': 'grep', 'source': self._metadata(sid), 'query': query}, candidates, max_chars)

    def _heading_ranges(self, sid, text):
        # A heading is eligible only if its entire line is visible.
        offset = 0
        for line in text.splitlines(keepends=True):
            end = offset + len(line)
            stripped = line.lstrip()
            if stripped.startswith('#') and stripped.lstrip('#').startswith(' ') and self._visible(sid, offset, end) == [(offset, end)]:
                yield offset, end
            offset = end

    def headings(self, sid, max_chars=None):
        self._begin()
        text = self._load(sid)
        return self._emit({'kind': 'headings', 'source': self._metadata(sid)},
                          [(sid, text, a, b) for a, b in self._heading_ranges(sid, text)], max_chars)

    def read_section(self, sid, heading_start, max_chars=None):
        self._begin()
        text = self._load(sid)
        headings = list(self._heading_ranges(sid, text))
        starts = [a for a, _ in headings]
        if heading_start not in starts:
            raise ValueError('invalid or restricted heading')
        idx = starts.index(heading_start)
        end = starts[idx + 1] if idx + 1 < len(starts) else len(text)
        return self._emit({'kind': 'section', 'source': self._metadata(sid), 'requested': [heading_start, end]},
                          [(sid, text, a, b) for a, b in self._visible(sid, heading_start, end)], max_chars)

    def finish(self, ranges, disposition, note):
        if self.finished or not isinstance(disposition, str) or not disposition or not isinstance(note, str):
            raise ValueError('invalid final disposition')
        items = []
        for r in ranges:
            sid, start, end = r['source_id'], r['start'], r['end']
            text = self._load(sid)
            self._validate_range(text, start, end)
            covered = start
            for _, a, b in sorted((s, a, b) for s, a, b in self.inspected if s == sid):
                if a <= covered: covered = max(covered, b)
                if covered >= end: break
            if covered < end:
                raise ValueError('final range was not inspected')
            items.append({'source': self._metadata(sid), **self._segment(text, start, end)})
        packet = {'kind': 'final', 'disposition': disposition, 'note': note, 'segments': items}
        cost = _tokens(packet)
        if cost > self.packet_tokens:
            raise ValueError('final packet exceeds budget')
        self.final_tokens = cost
        self.transcript.append(packet)
        self.finished = True
        return packet

    def save(self, path):
        Path(path).write_text(_json({'operations': self.operations, 'used_tokens': self.used_tokens,
            'budget_tokens': self.budget_tokens, 'packet_tokens': self.packet_tokens,
            'max_ops': self.max_ops, 'final_tokens': self.final_tokens, 'transcript': self.transcript}) + '\n', encoding='utf-8')

    @classmethod
    def load(cls, path, sources, allowed_ids):
        """Rebuild state by replaying and checking each stored output against sources.

        Callers must protect the state file from rollback or substitution; replay
        detects changes to sources and transcript content, not rollback of a
        previously valid file. No path in this file is used as a source route.
        """
        state = json.loads(Path(path).read_text(encoding='utf-8'))
        records = state['transcript']
        initial = []
        for record in records:
            if record['kind'] != 'initial': break
            segment = record['segments'][0]
            initial.append({'source_id': record['source']['id'], 'start': segment['start'], 'end': segment['end']})
        nav = cls(sources, allowed_ids, initial, state['budget_tokens'], state['packet_tokens'], state['max_ops'])
        if nav.transcript != records[:len(initial)]:
            raise ValueError('initial transcript changed')
        for expected in records[len(initial):]:
            kind = expected['kind']
            limit = expected.get('request_limit')
            if kind == 'menu': actual = nav.menu(limit)
            elif kind == 'read': actual = nav.read(expected['source']['id'], *expected['requested'], limit)
            elif kind == 'grep': actual = nav.grep(expected['source']['id'], expected['query'], limit)
            elif kind == 'headings': actual = nav.headings(expected['source']['id'], limit)
            elif kind == 'section': actual = nav.read_section(expected['source']['id'], expected['requested'][0], limit)
            elif kind == 'final':
                ranges = [{'source_id': x['source']['id'], 'start': x['start'], 'end': x['end']} for x in expected['segments']]
                actual = nav.finish(ranges, expected['disposition'], expected['note'])
            else: raise ValueError('unknown transcript operation')
            if actual != expected: raise ValueError('transcript mismatch')
        if nav.used_tokens != state['used_tokens'] or nav.final_tokens != state['final_tokens'] or not nav.operations <= state['operations'] <= nav.max_ops:
            raise ValueError('invalid session accounting')
        # Failed operations consume slots too, even though they produce no data.
        nav.operations = state['operations']
        return nav
