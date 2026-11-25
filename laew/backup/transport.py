"""Approved system-SFTP configuration and its worker-account trust boundary."""

import hashlib
from datetime import datetime, timezone
import os
from pathlib import Path
import stat

from .inventory import _inspect, backup_target_from_profile
from .policy import atomic_json, control_path, read_private_json
from .replication import OpenSSHTransport, ReplicationConfig, replicate_verified, test_connection
from .restore import _private


def current_identity():
    if os.name == "nt":
        from laew.security.windows_security import get_current_user_sid
        return get_current_user_sid()
    return str(os.geteuid())


def _system_executable(path):
    if _inspect(path) != path or not path.is_file():
        raise ValueError("System OpenSSH is unavailable.")
    for parent in (path, *path.parents):
        info = parent.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("OpenSSH path is not system controlled.")


def load_transport(path):
    fields = {"schema_version", "host", "port", "user", "remote_directory", "agent",
              "known_hosts", "known_hosts_sha256", "public_identity", "public_identity_sha256",
              "hardlink_qualified"}
    doc = read_private_json(Path(path))
    if type(doc) is not dict or set(doc) != fields or type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ValueError("Invalid protected SFTP configuration.")
    exe = Path("/usr/bin/sftp") if os.name == "posix" else Path(r"C:\Windows\System32\OpenSSH\sftp.exe")
    config = ReplicationConfig(doc["host"], doc["port"], doc["user"], doc["remote_directory"], exe,
                               Path(doc["known_hosts"]), Path(doc["public_identity"]), doc["agent"],
                               hardlink_qualified=doc["hardlink_qualified"])
    config.validate()
    return config


def _trust(path, expected, config):
    from laew.operator_cli import _bounded_file

    # Native Windows agent ownership and scheduled-token behavior still need an
    # adapter qualification. POSIX test and production execution do not share it.
    if os.name != "posix" or os.geteuid() == 0:
        raise ValueError("This worker identity has no qualified SSH agent boundary.")
    if load_transport(path) != expected:
        raise ValueError("Protected SFTP configuration changed.")
    doc = read_private_json(path)
    _system_executable(config.executable)
    _system_executable(config.executable.with_name("ssh"))
    for name in ("known_hosts", "public_identity"):
        value = _bounded_file(getattr(config, name), 65536, private=True)
        if hashlib.sha256(value).hexdigest() != doc[name + "_sha256"]:
            raise ValueError("Approved host pin or public identity changed.")
        if name == "public_identity" and not value.startswith((b"ssh-ed25519 ", b"ssh-rsa ", b"ecdsa-sha2-")):
            raise ValueError("Expected an OpenSSH public key.")
    agent = Path(config.agent)
    if not agent.is_absolute() or ".." in agent.parts or agent.parent.resolve(strict=True) != agent.parent:
        raise ValueError("Invalid dedicated SSH agent socket.")
    for ancestor in agent.parents:
        info = ancestor.lstat()
        if info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o022:
            raise ValueError("SSH agent ancestry permits replacement.")
    _private(agent.parent)
    info = agent.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("SSH agent socket is not worker private.")
    return True


def run_transport(args, config):
    from laew.operator_cli import _load_profile

    root = control_path(args.profile)
    if args.transport != root / "sftp.json":
        raise ValueError("The endpoint is not the installation's protected SFTP configuration.")
    path = root / "remote-health.json"
    previous = read_private_json(path) if path.exists() else {"connection": "not_tested", "remote": "unconfigured"}
    field = "connection" if args.action == "test-connection" else "remote"
    try:
        transport = OpenSSHTransport(config, trust=lambda active: _trust(args.transport, config, active))
        if field == "connection":
            state = test_connection(config, transport=transport)["state"]
        else:
            profile = _load_profile(str(args.profile))
            dest = backup_target_from_profile(profile)
            state = replicate_verified(config, destination=dest.destination, backup_id=args.id,
                                       release_record=args.release_record, staging_directory=root,
                                       transport=transport, expected_host=dest.host_id,
                                       expected_profile=dest.profile_id)["state"]
    except (OSError, ValueError, TypeError, RuntimeError):
        atomic_json(path, {**previous, field: "failed"})
        raise
    atomic_json(path, {**previous, field: state, field + "_at": datetime.now(timezone.utc).isoformat()})
