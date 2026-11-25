"""Protected operator actions and a bounded, read-only Workbench projection."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from .policy import (admission, atomic_json, control_path, initialize_policy, policy_revision, policy_state,
                     read_private_json, set_enabled)

_STATES = {"unconfigured", "enabled", "disabling", "disabled"}
_LOCAL = {"unconfigured", "validated", "unavailable"}
_LOCAL_BACKUP = {"unknown", "degraded", "ok"}
_CONNECTION = {"unconfigured", "not_tested", "connected", "failed"}
_REMOTE = {"unconfigured", "pending", "verified", "failed", "stale"}


def workbench_view(path, owner):
    """Expose only the reviewed projection, with no route to a writer operation."""
    empty = {"state": "unconfigured", "revision": None, "directories": [], "keys": [],
             "local": "unconfigured", "local_backup": "unknown", "connection": "unconfigured",
             "remote": "unconfigured", "observed_at": None}
    if not path or not owner:
        return empty
    try:
        from laew.operator_cli import _bounded_file, _unique_object
        from .health import _check_ancestry, _check_owner
        from .inventory import _inspect

        path = Path(path)
        if path.name != "backup-settings.json" or _inspect(path) != path:
            raise ValueError("Invalid view path.")
        _check_owner(path.parent, owner)
        _check_ancestry(path.parent, owner)
        _check_owner(path, owner)
        doc = json.loads(_bounded_file(path, 16384), object_pairs_hook=_unique_object)
        if (type(doc) is not dict or doc.keys() != empty.keys() or doc["state"] not in _STATES
                or doc["local"] not in _LOCAL or doc["local_backup"] not in _LOCAL_BACKUP
                or doc["connection"] not in _CONNECTION or doc["remote"] not in _REMOTE
                or not re.fullmatch(r"[a-f0-9]{64}", doc["revision"])):
            raise ValueError("Invalid view.")
        for field in ("directories", "keys"):
            if type(doc[field]) is not list or len(doc[field]) > 32 or any(
                    type(value) is not str or not 0 < len(value) <= 300 or not value.isprintable()
                    for value in doc[field]):
                raise ValueError("Invalid view choices.")
        observed = datetime.fromisoformat(doc["observed_at"])
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        if not 0 <= age <= 3600:
            doc.update(local_backup="unknown", connection="not_tested", remote="unconfigured")
        return doc
    except (OSError, ValueError, TypeError, RuntimeError, KeyError):
        return {**empty, "local": "unavailable"}


def _proposal(path):
    from laew.operator_cli import _bounded_file, _unique_object

    doc = json.loads(_bounded_file(Path(path), 16384), object_pairs_hook=_unique_object)
    if (type(doc) is not dict or doc.keys() != {"schema_version", "operation", "revision", "enabled",
                                               "directory", "host", "port", "user", "remote_directory", "key"}
            or type(doc["schema_version"]) is not int or doc["schema_version"] != 1
            or doc["operation"] not in ("settings", "test-connection", "validate-directory") or type(doc["enabled"]) is not bool
            or any(type(doc[key]) is not str or len(doc[key]) > 512 or not (doc[key].isprintable() or not doc[key])
                   for key in ("directory", "host", "user", "remote_directory", "key"))
            or (doc["port"] is not None and (type(doc["port"]) is not int or not 1 <= doc["port"] <= 65535))):
        raise ValueError("Invalid Workbench proposal.")
    return doc


def _validate_directory(profile, directory):
    from laew.operator_cli import _load_inventory, _load_profile
    from .archive import ArchiveLimits
    from .capture import _check_space, _snapshot, _sources
    from .restore import _private

    inventory = _load_inventory({**_load_profile(str(profile)), "destination": directory})
    _private(inventory.destination)
    limits = ArchiveLimits()
    tree, files, dirs = _snapshot(_sources(inventory), limits)
    _check_space(inventory.destination, tree, files, dirs, limits)
    return inventory


def _validate_proposal(args, operation, config=None):
    from laew.operator_cli import _load_inventory, _load_profile

    if args.proposal is None:
        raise ValueError("A reviewed Workbench proposal is required.")
    proposal = _proposal(args.proposal)
    if proposal["operation"] != operation or proposal["revision"] != policy_revision(args.profile):
        raise ValueError("The proposal does not match this reviewed profile revision.")
    if operation == "validate-directory":
        _validate_directory(args.profile, proposal["directory"])
        return proposal
    inventory = _load_inventory(_load_profile(str(args.profile)))
    if proposal["directory"] and Path(proposal["directory"]) != inventory.destination:
        raise ValueError("Review and provision the proposed destination as a new backup profile first.")
    endpoint = (proposal["host"], proposal["port"], proposal["user"], proposal["remote_directory"], proposal["key"])
    if any(endpoint) or operation == "test-connection":
        if config is None or endpoint != (config.host, config.port, config.user, config.remote_directory,
                                          config.public_identity.stem):
            raise ValueError("The proposal does not match the protected endpoint and selected key.")
    return proposal


def _view(profile, *, config=None, status_file=None):
    from laew.operator_cli import _load_inventory, _load_profile

    inv = _load_inventory(_load_profile(str(profile)))
    root = control_path(profile)
    local = {"directories": [str(inv.destination)], "keys": [config.public_identity.stem] if config else [],
             "local": "validated", "local_backup": "unknown",
             "connection": "unconfigured", "remote": "unconfigured"}
    if status_file is not None:
        from .health import summarize_status
        from .transport import current_identity

        local["local_backup"] = summarize_status(status_file, inv.profile_id, current_identity(),
                                                 datetime.now(timezone.utc))[0]
    state = policy_state(profile)
    if state != "unconfigured":
        path = root / "remote-health.json"
        if path.exists():
            data = read_private_json(path)
            if data["connection"] not in _CONNECTION or data["remote"] not in _REMOTE:
                raise ValueError("Invalid remote health.")
            local.update(connection=data["connection"], remote=data["remote"])
            now = datetime.now(timezone.utc)
            for field, fallback in (("connection", "not_tested"), ("remote", "stale")):
                if local[field] in ("connected", "verified"):
                    stamp = datetime.fromisoformat(data[field + "_at"])
                    if not 0 <= (now - stamp).total_seconds() <= 86400:
                        local[field] = fallback
    return {"state": state, "revision": policy_revision(profile),
            "observed_at": datetime.now(timezone.utc).isoformat(), **local}


def main(argv):
    from .provenance import validate_worker_media, validate_worker_runtime

    parser = argparse.ArgumentParser(prog="laew-backup-worker control", allow_abbrev=False)
    parser.add_argument("action", choices=("initialize", "view", "publish-view", "apply", "disable",
                                           "validate-directory", "test-connection", "replicate"))
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--transport", type=Path)
    parser.add_argument("--managed", action="store_true")
    parser.add_argument("--id")
    parser.add_argument("--release-record", type=Path)
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        validate_worker_runtime()
        validate_worker_media(args.profile)
        if args.action != "view" and not args.apply:
            raise ValueError("Protected operator action requires --apply.")
        config = None
        if args.action == "initialize":
            initialize_policy(args.profile, managed=args.managed)
        elif args.action == "disable":
            set_enabled(args.profile, enabled=False)
        else:
            from .transport import load_transport, run_transport

            config = load_transport(args.transport) if args.transport is not None else None
            if args.action == "publish-view":
                from .health import _check_ancestry, _check_owner
                from .inventory import _inspect
                from .transport import current_identity

                out = args.output
                if out is None or out.name != "backup-settings.json" or _inspect(out.parent) != out.parent:
                    raise ValueError("A protected Workbench projection directory is required.")
                from laew.operator_cli import _load_inventory, _load_profile
                from .inventory import _overlap
                inv = _load_inventory(_load_profile(str(args.profile)))
                if any(_overlap(out.parent, path) for path in
                       (inv.destination, inv.fence, args.profile.parent, *(s.path for s in inv.sources))):
                    raise ValueError("The projection directory overlaps private or source data.")
                _check_owner(out.parent, current_identity())
                _check_ancestry(out.parent, current_identity())
                view = _view(args.profile, config=config, status_file=args.status_file)
                atomic_json(out, view, mode=0o640 if os.name == "posix" else None)
            elif args.action == "apply":
                proposal = _validate_proposal(args, "settings", config)
                set_enabled(args.profile, enabled=proposal["enabled"], expected_revision=proposal["revision"])
            elif args.action == "validate-directory":
                _validate_proposal(args, args.action)
                print('{"state":"validated"}')
                return 0
            elif args.action in ("test-connection", "replicate"):
                if args.action == "test-connection":
                    _validate_proposal(args, args.action, config)
                elif config is None:
                    raise ValueError("Protected transport configuration required.")
                with admission(args.profile, operation=args.action):
                    run_transport(args, config)
        print(json.dumps(_view(args.profile, config=config, status_file=args.status_file), ensure_ascii=True))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, KeyError):
        print('{"state":"unavailable","error":"Protected backup control rejected the request."}')
        return 1
