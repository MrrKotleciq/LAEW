from datetime import datetime, timezone
import socket

from laew.status import collect_status, status_exit_code


def test_invalid_manifest_sanitized(tmp_path):
    result = collect_status(tmp_path / 'secret-name')
    assert status_exit_code(result) == 2
    assert 'secret-name' not in str(result)


def test_default_no_network_or_writes(tmp_path, monkeypatch):
    source = __import__('pathlib').Path('manifests/SYSTEM_MANIFEST.yaml').read_text(encoding='utf-8')
    manifest = tmp_path / 'manifest.yaml'
    manifest.write_text(source, encoding='utf-8')
    before = set(tmp_path.iterdir())
    def forbidden(*args, **kwargs):
        raise AssertionError('network used')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    result = collect_status(manifest, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert set(tmp_path.iterdir()) == before
    assert result['schema_version'] == 1
    assert status_exit_code(result) == 1
    assert next(c for c in result['checks'] if c['component'] == 'provider')['reason'] == 'not_probed'


def test_non_loopback_probe_is_refused(tmp_path):
    source = __import__('pathlib').Path('manifests/SYSTEM_MANIFEST.yaml').read_text(encoding='utf-8').replace('host: "127.0.0.1"', 'host: "192.0.2.1"')
    manifest = tmp_path / 'manifest.yaml'
    manifest.write_text(source, encoding='utf-8')
    result = collect_status(manifest, probe=True)
    assert next(c for c in result['checks'] if c['component'] == 'provider')['reason'] == 'endpoint_not_approved'


def test_operator_invalid_status_uses_json_without_echoing_inputs(tmp_path, capsys):
    import json
    from laew.operator_cli import dispatch

    assert dispatch(['status', '--manifest', str(tmp_path / 'private-path'), '--json']) == 2
    response = capsys.readouterr()
    assert not response.err
    assert 'private-path' not in response.out
    assert json.loads(response.out)['checks'][0]['reason'] == 'invalid_config'


def test_required_and_optional_truth_table():
    from laew.status import _overall
    def c(state, required):
        return {'state': state, 'required': required}
    assert _overall([c('ok', True), c('unknown', False)]) == 'ok'
    assert _overall([c('unknown', True)]) == 'degraded'
    assert _overall([c('unavailable', False)]) == 'degraded'
    assert _overall([c('unavailable', True)]) == 'unavailable'
    assert _overall([c('disabled', False)]) == 'ok'


def test_marker_identity_age_and_interrupted(tmp_path, monkeypatch):
    import hashlib
    import json
    import os
    import tempfile
    from laew.rag.identity import project_collection_name
    from laew.status import _rag_marker
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    vector = {'host': 'localhost', 'port': 8000, 'global_collection': 'laew_global'}
    directory = tmp_path / 'laew-collection-locks'
    directory.mkdir()
    key = json.dumps(['loopback', 8000, project_collection_name(tmp_path)])
    marker = directory / (hashlib.sha256(key.encode()).hexdigest() + '.lock')
    marker.write_text(json.dumps({'state': 'complete', 'generation': 'test'}))
    os.utime(marker, (1000, 1000))
    now = datetime.fromtimestamp(1100, timezone.utc)
    assert _rag_marker(vector, tmp_path, 'project', now, None)['state'] == 'unknown'
    assert _rag_marker(vector, tmp_path, 'project', now, 100)['state'] == 'ok'
    assert _rag_marker(vector, tmp_path, 'project', now, 99)['reason'] == 'stale_marker'
    assert _rag_marker(vector, tmp_path, 'global', now, 100)['reason'] == 'no_cached_state'
    marker.write_text('{"state":"incomplete","generation":"test"}')
    assert _rag_marker(vector, tmp_path, 'project', now, 100)['reason'] == 'sync_interrupted_or_in_progress'
    marker.write_text('{invalid')
    assert _rag_marker(vector, tmp_path, 'project', now, 100)['reason'] == 'invalid_marker'


def test_probe_refuses_external_and_malformed(monkeypatch):
    import time
    from laew.status import _probe_http, _provider_response
    class FakeSocket:
        def __init__(self, *args): self.chunks = [b'HTTP/1.1 302 Found\r\nLocation: http://192.0.2.1\r\n\r\n', b'']
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): pass
        def connect(self, addr): pass
        def sendall(self, data): pass
        def recv(self, size): return self.chunks.pop(0)
    monkeypatch.setattr(socket, 'socket', FakeSocket)
    assert _probe_http('192.0.2.1', 80, '/', time.monotonic()+3, _provider_response)[1] == 'endpoint_not_approved'
    assert _probe_http('127.0.0.1', 80, '/', time.monotonic()+3, _provider_response)[1] == 'probe_http_error'


def test_dribbling_probe_has_absolute_deadline(monkeypatch):
    import laew.status as status
    clock = [0.0]
    class FakeSocket:
        def __init__(self, *args): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): assert value > 0
        def connect(self, addr): pass
        def sendall(self, data): pass
        def recv(self, size):
            clock[0] += .2
            return b'x'
    monkeypatch.setattr(status.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(socket, 'socket', FakeSocket)
    assert status._probe_http('127.0.0.1', 80, '/', 3, status._provider_response)[1] == 'probe_deadline'
    assert clock[0] <= 1.2


def test_backup_cached_receipts_fresh_stale_and_invalid(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    import laew.backup.inventory as inventory
    import laew.backup.archive as archive
    source = __import__('pathlib').Path('manifests/SYSTEM_MANIFEST.yaml').read_text(encoding='utf-8')
    manifest = tmp_path / 'manifest.yaml'
    manifest.write_text(source, encoding='utf-8')
    destination = tmp_path / 'destination'
    destination.mkdir()
    (destination / 'one.receipt.json').write_text('{}')
    target = SimpleNamespace(destination=destination, profile_id='p', host_id='h')
    monkeypatch.setattr(inventory, 'backup_target_from_profile', lambda p: target)
    record = {'profile_id': 'p', 'host_id': 'h', 'verified_at': '2026-01-01T00:00:00+00:00'}
    monkeypatch.setattr(archive, 'read_receipt', lambda *args: record)
    def backup_at(day):
        result = collect_status(manifest, backup_profile={}, now=datetime(2026, 1, day, tzinfo=timezone.utc))
        return next(c for c in result['checks'] if c['component'] == 'backup')
    assert backup_at(2)['state'] == 'ok'
    assert backup_at(3)['reason'] == 'stale_receipt'
    record['host_id'] = 'other'
    assert backup_at(2)['reason'] == 'no_valid_receipt'


def test_telemetry_policy_states(tmp_path, monkeypatch):
    import json
    import laew.security.protected_profile as protected
    from laew.status import _telemetry_status
    monkeypatch.setattr(protected, 'read_telemetry_root', lambda path: tmp_path)
    enabled = {'telemetry': {'enabled': True}}
    assert _telemetry_status(enabled, None)['reason'] == 'no_quota_state'
    policy = tmp_path / '.quota.json'
    policy.write_text(json.dumps({'version': 1, 'run_bytes': 262144, 'total_bytes': 268435456}))
    assert _telemetry_status(enabled, None)['state'] == 'ok'
    policy.write_text('{}')
    assert _telemetry_status(enabled, None)['reason'] == 'invalid_quota_state'


def test_probe_rejects_truncated_and_malformed_response(monkeypatch):
    import time
    from laew.status import _probe_http, _provider_response
    responses = iter([b'HTTP/1.0 200 OK\r\nContent-Length: 100\r\n\r\n{"data":[]}', b''])
    class FakeSocket:
        def __init__(self, *args): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): pass
        def connect(self, addr): pass
        def sendall(self, data): pass
        def recv(self, size): return next(responses)
    monkeypatch.setattr(socket, 'socket', FakeSocket)
    assert _probe_http('127.0.0.1', 80, '/', time.monotonic()+3, _provider_response)[1] == 'probe_invalid_response'


def test_probe_stalled_loopback_is_bounded():
    import threading
    import time
    from laew.status import _probe_http, _provider_response
    server = socket.socket()
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    def serve():
        conn, _ = server.accept()
        with conn:
            conn.recv(4096)
            time.sleep(1.2)
    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    start = time.monotonic()
    try:
        state, reason = _probe_http('127.0.0.1', server.getsockname()[1], '/v1/models', start + 3, _provider_response)
        assert (state, reason) == ('unavailable', 'probe_deadline')
        assert time.monotonic() - start < 1.8
    finally:
        server.close()
        worker.join(2)
