import hashlib
import json

import pytest

from laew.eval.evidence_navigation import NavigationSession, Source


@pytest.fixture
def source(tmp_path):
    text = '# Public\nalpha secret omega\n# Hidden heading\nbeta alpha\n# End\nlast\n'
    path = tmp_path / 'source.txt'
    path.write_bytes(text.encode())
    secret = text.index('secret')
    hidden = text.index('# Hidden')
    return Source('doc', 'global', 'r1', hashlib.sha256(text.encode()).hexdigest(), path,
                  'v1', ((secret, secret + 6), (hidden, hidden + len('# Hidden heading\n')))), text


def session(source, **kw):
    return NavigationSession([source], ['doc'], **kw)


def test_restricted_read_segments_and_final_roundtrip(source, tmp_path):
    s, text = source
    nav = session(s)
    result = nav.read('doc', 0, len(text))
    assert len(result['segments']) == 3
    assert all('secret' not in x['text'] and 'Hidden' not in x['text'] for x in result['segments'])
    for segment in result['segments']:
        assert text[segment['start']:segment['end']] == segment['text']
    seg = result['segments'][1]
    packet = nav.finish([{'source_id': 'doc', 'start': seg['start'], 'end': seg['end']}], 'answer', 'ok')
    assert packet['segments'][0]['text'] == seg['text']
    path = tmp_path / 'transcript.json'
    nav.save(path)
    assert json.loads(path.read_text(encoding='utf-8'))['transcript'][-1] == packet


def test_headings_grep_and_unseen_rejected(source):
    s, text = source
    nav = session(s)
    headers = nav.headings('doc')
    assert [x['text'].strip() for x in headers['segments']] == ['# Public', '# End']
    hits = nav.grep('doc', 'alpha')
    assert len(hits['segments']) == 2
    assert all('secret' not in x['text'] for x in hits['segments'])
    assert hits['segments'][0]['line_start'] == 2
    with pytest.raises(ValueError, match='not inspected'):
        nav.finish([{'source_id': 'doc', 'start': text.index('last'), 'end': len(text)}], 'answer', '')


def test_hash_and_authorization_are_checked_every_time(source):
    s, text = source
    nav = session(s)
    nav.menu()
    s.path.write_bytes((text + 'changed').encode())
    with pytest.raises(ValueError, match='hash mismatch'):
        nav.read('doc', 0, 1)
    with pytest.raises(ValueError):
        NavigationSession([s], ['missing'])
    bad = Source('other', 'private', 'r', s.sha256, s.path, 'v1')
    with pytest.raises(ValueError):
        session(bad).menu()


def test_budget_counts_repeats_and_caps_output(source):
    s, text = source
    nav = session(s, budget_tokens=500, packet_tokens=100, max_ops=3)
    first = nav.read('doc', 0, len(text), max_chars=500)
    first_cost = nav.used_tokens
    assert len(json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(',', ':'))) <= 500
    nav.read('doc', 0, len(text), max_chars=500)
    assert nav.used_tokens == first_cost * 2
    nav.menu()
    nav.read('doc', 0, 1)
    with pytest.raises(ValueError, match='operation limit'):
        nav.read('doc', 0, 1)


def test_section_initial_packet_and_range_validation(source):
    s, text = source
    nav = session(s, initial_packets=[{'source_id':'doc', 'start': 0, 'end': 8}])
    assert nav.used_tokens > 0
    with pytest.raises(ValueError, match='restricted'):
        nav.read_section('doc', text.index('# Hidden'))
    with pytest.raises(ValueError, match='invalid range'):
        nav.read('doc', -1, 4)
    with pytest.raises(ValueError, match='restricted'):
        session(s, initial_packets=[{'source_id':'doc', 'start': 0, 'end': len(text)}])


def test_final_cannot_bridge_visible_segments(source):
    s, text = source
    nav = session(s)
    nav.read('doc', 0, len(text))
    with pytest.raises(ValueError, match='not inspected'):
        nav.finish([{'source_id': 'doc', 'start': 0, 'end': len(text)}], 'answer', '')


def test_saved_session_replay_and_tamper(source, tmp_path):
    s, text = source
    nav = session(s)
    nav.read_lines('doc', 1, 2, max_chars=600)
    path = tmp_path / 'state.json'
    nav.save(path)
    resumed = NavigationSession.load(path, [s], ['doc'])
    assert resumed.used_tokens == nav.used_tokens
    assert resumed.operations == 1
    resumed.headings('doc')
    state = json.loads(path.read_text(encoding='utf-8'))
    state['transcript'][0]['segments'][0]['text'] = 'forged'
    path.write_text(json.dumps(state), encoding='utf-8')
    with pytest.raises(ValueError, match='mismatch'):
        NavigationSession.load(path, [s], ['doc'])


def test_final_packet_budget_and_initial_tampering(source):
    s, text = source
    nav = session(s, packet_tokens=100)
    result = nav.read('doc', 0, len(text))
    seg = result['segments'][0]
    with pytest.raises(ValueError, match='budget'):
        nav.finish([{'source_id': 'doc', 'start': seg['start'], 'end': seg['end']}], 'answer', 'x' * 500)


def test_menu_free_final_separate_and_union(source):
    s, text = source
    nav = session(s, budget_tokens=700, packet_tokens=300)
    menu = nav.menu()
    assert str(s.path) not in json.dumps(menu)
    assert nav.operations == 0
    nav.read('doc', 0, 4)
    nav.read('doc', 4, 8)
    before = nav.used_tokens
    packet = nav.finish([{'source_id':'doc', 'start':0, 'end':8}], 'answer', '')
    assert packet['segments'][0]['text'] == text[:8]
    assert nav.used_tokens == before and nav.final_tokens > 0


def test_case_insensitive_grep_and_explicit_holes(source):
    s, text = source
    nav = session(s)
    hits = nav.grep('doc', 'ALPHA')
    assert len(hits['segments']) == 2
    read = nav.read('doc', 0, len(text))
    assert [(x['start'], x['end']) for x in read['omissions'] if x['reason'] == 'restricted'] == list(s.restricted_ranges)
    clipped = nav.read('doc', 0, len(text), 470)
    assert any(x['reason'] == 'budget' for x in clipped['omissions'])


def test_failed_output_is_atomic_and_lines_consume_operation(tmp_path):
    text = 'x\n' + 'z' * 10000 + '\nx\n'
    path = tmp_path / 's.txt'
    path.write_bytes(text.encode())
    s = Source('doc', 'global', 'r', hashlib.sha256(text.encode()).hexdigest(), path, 'v1', ((2, 10003),))
    nav = session(s)
    with pytest.raises(ValueError):
        nav.grep('doc', 'x', max_chars=399)
    assert nav.inspected == [] and nav.transcript == [] and nav.used_tokens == 0
    with pytest.raises(ValueError, match='not inspected'):
        nav.finish([{'source_id':'doc', 'start':0, 'end':1}], 'answer', '')
    with pytest.raises(ValueError, match='line range'):
        nav.read_lines('doc', 0, 1)
    assert nav.operations == 2
