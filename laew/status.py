"""Read-only operator health snapshot. Never initializes application services."""
from datetime import datetime, timezone
import ipaddress
import hashlib
import math
import stat
import tempfile
import json
import os
from pathlib import Path
import shutil
import socket
import time

from laew.manifest import load_manifest
from laew.rag.config import manifest_base_dir, resolve_project_root


def _check(component, state, reason, source, **extra):
    return dict(component=component, state=state, reason=reason, source=source, **extra)


def _probe_http(host, port, route, deadline, valid_body):
    # Use a fixed GET and absolute receive deadline. Per-socket inactivity
    # timeouts alone do not bound a peer that sends a byte at a time.
    if host == "localhost":
        host = "127.0.0.1"
    try:
        address = ipaddress.ip_address(host) if type(host) is str else None
    except ValueError:
        return "unknown", "endpoint_not_approved"
    if address is None or not address.is_loopback or type(port) is not int or not 1 <= port <= 65535:
        return "unknown", "endpoint_not_approved"
    def remaining():
        budget = min(deadline, started + 1.0) - time.monotonic()
        if budget <= 0:
            raise TimeoutError
        return budget
    started = time.monotonic()
    try:
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as conn:
            conn.settimeout(remaining())
            conn.connect((str(address), port))
            conn.settimeout(remaining())
            conn.sendall(f"GET {route} HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode("ascii"))
            payload = bytearray()
            while len(payload) <= 65536:
                conn.settimeout(remaining())
                chunk = conn.recv(min(4096, 65537 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
        header, separator, body = payload.partition(b"\r\n\r\n")
        if len(payload) > 65536 or not separator:
            return "unknown", "probe_invalid_response"
        status = header.split(b"\r\n", 1)[0].split(b" ")
        if len(status) < 2 or status[0] not in (b"HTTP/1.0", b"HTTP/1.1") or status[1] != b"200":
            return "unavailable", "probe_http_error"
        fields = {}
        for line in header.split(b"\r\n")[1:]:
            name, separator, value = line.partition(b":")
            if not separator or not name:
                return "unknown", "probe_invalid_response"
            name = name.strip().lower()
            if name in fields:
                return "unknown", "probe_invalid_response"
            fields[name] = value.strip()
        if b"transfer-encoding" in fields:
            return "unknown", "probe_invalid_response"
        if b"content-length" in fields and (not fields[b"content-length"].isdigit() or int(fields[b"content-length"]) != len(body)):
            return "unknown", "probe_invalid_response"
        if not valid_body(json.loads(body)):
            return "unknown", "probe_invalid_response"
        return "ok", "reachable"
    except TimeoutError:
        return "unavailable", "probe_deadline"
    except (ValueError, TypeError, UnicodeError):
        return "unknown", "probe_invalid_response"
    except OSError:
        return "unavailable", "probe_failed"


def _provider_response(data):
    return type(data) is dict and type(data.get("data")) is list


def _heartbeat_response(data):
    return type(data) is dict and type(data.get("nanosecond heartbeat")) is int


def _telemetry_status(manifest, manifest_path):
    if not manifest.get("telemetry", {}).get("enabled", False):
        return _check("telemetry", "disabled", "not_configured", "config")
    try:
        from laew.security.protected_profile import read_telemetry_root
        from laew.telemetry import inspect_telemetry_storage

        root = read_telemetry_root(manifest_path)
        if root is None:
            return _check("telemetry", "unknown", "protected_profile_unobserved", "config")
        state, reason = inspect_telemetry_storage(root)
        return _check("telemetry", state, reason, "cache")
    except (OSError, ValueError, TypeError, KeyError):
        return _check("telemetry", "unavailable", "protected_storage_unverified", "filesystem")


def _marker_temp_root():
    # gettempdir() can create files while selecting a directory.  Use its
    # already-cached value, or the explicit environment/default only.
    if tempfile.tempdir:
        return Path(os.fsdecode(tempfile.tempdir))
    for name in ("TMPDIR", "TEMP", "TMP"):
        value = os.environ.get(name)
        if value and Path(value).is_absolute():
            return Path(value)
    return Path("/tmp") if os.name != "nt" else None


def _rag_marker(vector, root, scope, now, threshold):
    from laew.rag.identity import project_collection_name

    component = "rag_" + scope + "_freshness"
    try:
        host = str(vector.get("host", "localhost")).casefold().strip("[]")
        if host in {"localhost", "127.0.0.1", "::1"}:
            host = "loopback"
        port = int(vector.get("port", 8000))
        collection = project_collection_name(root) if scope == "project" else vector.get("global_collection", "laew_global")
        key = json.dumps([host, port, collection])
        temp_root = _marker_temp_root()
        if temp_root is None:
            return _check(component, "unknown", "marker_location_unknown", "cache")
        marker = temp_root / "laew-collection-locks" / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".lock")
        before = marker.lstat()
        if not stat.S_ISREG(before.st_mode) or getattr(before, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT or before.st_size > 4096:
            return _check(component, "unknown", "invalid_marker", "cache")
        with marker.open("rb") as stream:
            if not os.path.samestat(before, os.fstat(stream.fileno())):
                raise ValueError("changed")
            data = stream.read(4097)
            after = os.fstat(stream.fileno())
        if len(data) != before.st_size or after.st_mtime_ns != before.st_mtime_ns or after.st_size != before.st_size:
            raise ValueError("changed")
        marker_data = json.loads(data)
        if not isinstance(marker_data, dict):
            raise ValueError("invalid")
        if marker_data.get("state") != "complete":
            return _check(component, "degraded", "sync_interrupted_or_in_progress", "cache")
        if not isinstance(marker_data.get("generation"), str) or not marker_data["generation"]:
            raise ValueError("invalid")
        age = now.timestamp() - before.st_mtime
        if age < 0:
            return _check(component, "unknown", "marker_in_future", "cache")
        if threshold is None:
            return _check(component, "unknown", "freshness_policy_not_supplied", "cache", age_seconds=age)
        return _check(component, "ok" if age <= threshold else "degraded",
                      "cached_marker_within_policy" if age <= threshold else "stale_marker", "cache", age_seconds=age)
    except FileNotFoundError:
        return _check(component, "unknown", "no_cached_state", "cache")
    except (OSError, ValueError, TypeError, OverflowError):
        return _check(component, "unknown", "invalid_marker", "cache")


def _overall(checks):
    if any(c["required"] and c["state"] == "unavailable" for c in checks):
        return "unavailable"
    if any(c["state"] in {"degraded", "unavailable"} or
           (c["required"] and c["state"] == "unknown") for c in checks):
        return "degraded"
    return "ok"


def collect_status(manifest_path, *, probe=False, backup_profile=None, now=None, rag_max_age_seconds=None):
    """Return a sanitized v1 snapshot; only explicit probe may open loopback sockets."""
    now = now or datetime.now(timezone.utc)
    if (rag_max_age_seconds is not None and
            (type(rag_max_age_seconds) not in (int, float) or not math.isfinite(rag_max_age_seconds) or rag_max_age_seconds < 0)):
        raise ValueError("invalid RAG freshness threshold")
    checks = []
    def add(*args, **kwargs):
        checks.append(_check(*args, **kwargs))
    try:
        manifest = load_manifest(manifest_path)
        root = resolve_project_root(manifest, base_dir=manifest_base_dir(manifest_path))
    except (Exception):
        add('manifest', 'unavailable', 'invalid_config', 'config', required=True)
        return {'schema_version': 1, 'observed_at': now.isoformat(), 'overall': 'unavailable', 'checks': checks}
    add('manifest', 'ok', 'valid', 'config')
    add('workspace', 'ok' if root.is_dir() and os.access(root, os.R_OK | os.X_OK) else 'unavailable',
        'accessible' if root.is_dir() and os.access(root, os.R_OK | os.X_OK) else 'inaccessible', 'filesystem')
    session = (manifest.get('memory', {}).get('session', {}) or {}).get('storage', 'runtime/sessions')
    try:
        session_path = Path(session).expanduser()
        if not session_path.is_absolute():
            session_path = manifest_base_dir(manifest_path) / session_path
        state = 'ok' if session_path.is_dir() and os.access(session_path, os.R_OK | os.X_OK) else 'unknown'
        add('sessions', state, 'accessible' if state == 'ok' else 'not_present_or_inaccessible', 'filesystem')
    except (TypeError, ValueError, OSError):
        add('sessions', 'unknown', 'invalid_path', 'config')
    try:
        free = shutil.disk_usage(root).free
        add('disk', 'ok', 'measured', 'filesystem', free_bytes=free)
    except OSError:
        add('disk', 'unknown', 'measurement_unavailable', 'filesystem')
    add('process', 'ok', 'partially_measured', 'filesystem', cpu_seconds=time.process_time(), elapsed_seconds=None)
    checks.append(_telemetry_status(manifest, manifest_path))
    providers = ((manifest.get('agent', {}) or {}).get('llm', {}) or {}).get('providers', []) or []
    deadline = time.monotonic() + 3.0
    role_map = ((manifest.get('agent', {}) or {}).get('llm', {}) or {}).get('roles', {}) or {}
    required_provider_names = {name for choices in role_map.values() if isinstance(choices, list) for name in choices if isinstance(name, str)} if isinstance(role_map, dict) else set()
    provider_required = []
    if not providers:
        add('provider', 'disabled', 'not_configured', 'config')
    else:
        for provider in providers:
            provider_required.append(not required_provider_names or (isinstance(provider, dict) and provider.get('name') in required_provider_names))
            if not isinstance(provider, dict):
                add('provider', 'unknown', 'invalid_config', 'config')
            elif not probe:
                add('provider', 'unknown', 'not_probed', 'config')
            elif provider.get('type') not in ('llama.cpp', 'llamacpp'):
                add('provider', 'unknown', 'probe_unsupported', 'config')
            else:
                state, reason = _probe_http(provider.get("host", "127.0.0.1"), provider.get("port", 8080),
                                            "/v1/models", deadline, _provider_response)
                add('provider', state, reason, 'probe')
    configured_names = {p.get('name') for p in providers if isinstance(p, dict) and isinstance(p.get('name'), str)}
    for _ in required_provider_names - configured_names:
        add('provider', 'unavailable', 'required_provider_not_configured', 'config')
        provider_required.append(True)
    vector = (manifest.get('rag', {}).get('vector_store', {}) or {})
    if not vector.get('enabled', False):
        add('chroma', 'disabled', 'not_configured', 'config')
        add('rag_project_freshness', 'disabled', 'not_configured', 'config')
        add('rag_global_freshness', 'disabled', 'not_configured', 'config')
    else:
        if probe:
            if vector.get("ssl"):
                state, reason = "unknown", "probe_unsupported"
            else:
                state, reason = _probe_http(vector.get("host", "localhost"), vector.get("port", 8000),
                                            "/api/v2/heartbeat", deadline, _heartbeat_response)
            add("chroma", state, reason, "probe")
        else:
            add('chroma', 'unknown', 'not_probed', 'config')
        checks.extend(_rag_marker(vector, root, scope, now, rag_max_age_seconds) for scope in ('project', 'global'))
    for component, env_name, subdir, filename in (
        ('memory_database', 'LAEW_MEMORY_STORAGE', 'memory', 'memory.db'),
        ('knowledge_database', 'LAEW_KNOWLEDGE_STORAGE', 'knowledge', 'curation.db'),
    ):
        try:
            path = Path(os.environ[env_name]) if os.environ.get(env_name) else session_path.parent / subdir / filename
            if not path.exists():
                add(component, 'unknown', 'not_present', 'filesystem')
            elif path.is_file() and os.access(path, os.R_OK):
                add(component, 'ok', 'metadata_accessible', 'filesystem')
            else:
                add(component, 'unavailable', 'inaccessible', 'filesystem')
        except (OSError, ValueError, UnboundLocalError):
            add(component, 'unknown', 'metadata_unavailable', 'filesystem')
    if backup_profile is None:
        add('backup', 'disabled', 'profile_not_supplied', 'config')
    else:
        try:
            from laew.backup.inventory import backup_target_from_profile
            from laew.backup.archive import read_receipt
            target = backup_target_from_profile(backup_profile)
            latest = None
            # Bounded enumeration; do not follow symlinks or inspect archive contents.
            with os.scandir(target.destination) as entries:
                for i, entry in enumerate(entries):
                    if i >= 10000:
                        raise ValueError('too many entries')
                    if not entry.name.endswith('.receipt.json'):
                        continue
                    try:
                        receipt = read_receipt(target.destination, entry.name[:-13])
                        if receipt['profile_id'] != target.profile_id or receipt['host_id'] != target.host_id:
                            continue
                        stamp = datetime.fromisoformat(receipt['verified_at'])
                        if stamp <= now and (latest is None or stamp > latest):
                            latest = stamp
                    except (ValueError, OSError):
                        continue
            if latest is None:
                add('backup', 'unknown', 'no_valid_receipt', 'cache')
            else:
                age = (now - latest).total_seconds()
                add('backup', 'ok' if age <= 86400 else 'degraded', 'cached_receipt' if age <= 86400 else 'stale_receipt', 'cache', age_seconds=age)
        except (ValueError, OSError, KeyError, TypeError):
            add('backup', 'unknown', 'profile_or_receipt_unavailable', 'cache')
    required_components = {'manifest', 'workspace', 'sessions', 'disk'}
    if vector.get('enabled', False):
        required_components.update(('chroma', 'rag_project_freshness', 'rag_global_freshness'))
    if backup_profile is not None:
        required_components.add('backup')
    provider_index = 0
    for check in checks:
        required = check['component'] in required_components
        if check['component'] == 'provider' and provider_required:
            required = provider_required[provider_index]
            provider_index += 1
        check['required'] = required and check['state'] != 'disabled'
    overall = _overall(checks)
    return {'schema_version': 1, 'observed_at': now.isoformat(), 'overall': overall, 'checks': checks}


def status_exit_code(result):
    return {'ok': 0, 'degraded': 1, 'unavailable': 2}[result['overall']]
