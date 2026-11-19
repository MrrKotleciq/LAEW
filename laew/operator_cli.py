"""Operator inspection and explicitly acknowledged backup capture commands.

This module neither provisions storage nor establishes a protected profile.
The caller must verify authorization, isolation and root disjointness before
returning a root from the resolver. Without a resolver telemetry is disabled.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import UUID

from laew.telemetry import read_run, summarize_events
from laew.backup.archive import read_receipt, verify_archive
from laew.backup.inventory import backup_target_from_profile, build_inventory
from laew.manifest import validate_manifest
import yaml


class _InvalidArguments(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # Never display argparse's input-dependent diagnostics.
        raise _InvalidArguments


_HELP = {
    ("backup",): "usage: laew backup {plan,list,verify,create} ...\n\nBackup inspection and explicitly authorized capture commands.",
    ("backup", "plan"): "usage: laew backup plan --profile PROFILE [--json]\n\nInspect declared source inventory.",
    ("backup", "list"): "usage: laew backup list --profile PROFILE [--json]\n\nList cached committed receipts; does not verify archive contents.",
    ("backup", "verify"): "usage: laew backup verify --profile PROFILE --id ID [--json]\n\nVerify the complete archive and receipt.",
    ("backup", "create"): "usage: laew backup create --profile PROFILE --acknowledgement ABS --apply [--json]\n\nCapture an explicitly quiesced installation.",
    ("telemetry",): "usage: laew telemetry {show} ...\n\nRead-only telemetry inspection commands.",
    ("telemetry", "show"): "usage: laew telemetry show RUN_ID [--manifest PATH] [--json]\n\nInspect a telemetry trace by UUID.",
    ("restore",): "usage: laew restore --profile PROFILE --id ID (--verify-only | --target ABS --apply) [--project-root ABS] [--json]\n\nVerify or publish an isolated restore.",
}


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="laew", add_help=False)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    telemetry = commands.add_parser("telemetry", add_help=False)
    actions = telemetry.add_subparsers(dest="action", required=True, parser_class=_Parser)
    show = actions.add_parser("show", add_help=False)
    show.add_argument("run_id")
    show.add_argument("--manifest")
    show.add_argument("--json", action="store_true")
    backup = commands.add_parser("backup", add_help=False)
    backup_actions = backup.add_subparsers(dest="action", required=True, parser_class=_Parser)
    for name in ("plan", "list", "verify", "create"):
        action = backup_actions.add_parser(name, add_help=False)
        action.add_argument("--profile", required=True)
        action.add_argument("--json", action="store_true")
        if name == "verify":
            action.add_argument("--id", required=True)
        if name == "create":
            action.add_argument("--acknowledgement", required=True)
            action.add_argument("--apply", action="store_true", required=True)
    restore = commands.add_parser("restore", add_help=False)
    restore.add_argument("--profile", required=True)
    restore.add_argument("--id", required=True)
    mode = restore.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--target")
    restore.add_argument("--apply", action="store_true")
    restore.add_argument("--project-root", action="append", default=[])
    restore.add_argument("--json", action="store_true")
    return parser


def _result(state: str, *, run_id: str | None = None,
            error_code: str | None = None, events: list | None = None) -> dict:
    records = events if events is not None else []
    return {
        "schema_version": 1,
        "command": "telemetry.show",
        "state": state,
        "run_id": run_id,
        "error_code": error_code,
        "summary": summarize_events(records, state),
        "events": records,
    }


def _display(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, separators=(",", ":"), allow_nan=False))
        return
    print("Telemetry: " + result["state"])
    if result["run_id"] is not None:
        print("Run: " + result["run_id"])
    if result["error_code"] is not None:
        print("Error: " + result["error_code"])
    if result["events"]:
        print("Events: " + str(result["summary"]["event_count"]))
        if result["summary"]["status"] is not None:
            print("Outcome: " + result["summary"]["status"])
        for event in result["events"]:
            print(json.dumps(event, separators=(",", ":"), allow_nan=False))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _bounded_file(path: Path, limit: int) -> bytes:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid path")
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        if (stat.S_ISLNK(info.st_mode) or getattr(component, "is_junction", lambda: False)()
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise ValueError("linked path")
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("invalid file")
    if info.st_size > limit:
        raise ValueError("oversized")
    with path.open("rb") as stream:
        if not os.path.samestat(info, os.fstat(stream.fileno())):
            raise ValueError("changed")
        data = stream.read(limit + 1)
    if len(data) != info.st_size or len(data) > limit:
        raise ValueError("changed")
    return data


def _load_profile(profile_path: str):
    profile = json.loads(_bounded_file(Path(profile_path), 65536), object_pairs_hook=_unique_object)
    if type(profile) is not dict or type(profile.get("manifest_path")) is not str:
        raise ValueError("invalid profile")
    return profile


def _load_inventory(profile):
    manifest = yaml.safe_load(_bounded_file(Path(profile["manifest_path"]), 1048576))
    if type(manifest) is not dict:
        raise ValueError("invalid manifest")
    validate_manifest(manifest)
    return build_inventory(profile, manifest)


def _canonical_uuid(value: str) -> str:
    identifier = str(UUID(value))
    if identifier != value:
        raise ValueError("invalid identifier")
    return identifier


def _load_acknowledgement(path: str):
    from laew.backup.capture import WriterAcknowledgement

    doc = json.loads(_bounded_file(Path(path), 65536), object_pairs_hook=_unique_object)
    required = {"schema_version", "profile_id", "host_id", "backup_id", "cut_id", "roster", "stopped",
                "inventory_complete", "restart_inhibited", "valid_until"}
    if type(doc) is not dict or set(doc) != required or type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ValueError("invalid acknowledgement")
    backup_id = _canonical_uuid(doc["backup_id"])
    cut_id = _canonical_uuid(doc["cut_id"])
    if any(type(doc[key]) is not str or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", doc[key]) for key in ("profile_id", "host_id")):
        raise ValueError("invalid acknowledgement")
    if doc["inventory_complete"] is not True or doc["restart_inhibited"] is not True:
        raise ValueError("invalid acknowledgement")
    for key in ("roster", "stopped"):
        owners = doc[key]
        if (type(owners) is not list or not 0 < len(owners) <= 256 or
                any(type(owner) is not str or owner == "unknown" or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", owner) for owner in owners) or
                len(set(owners)) != len(owners)):
            raise ValueError("invalid acknowledgement")
    if set(doc["roster"]) != set(doc["stopped"]):
        raise ValueError("invalid acknowledgement")
    if type(doc["valid_until"]) is not str or len(doc["valid_until"]) > 40:
        raise ValueError("invalid acknowledgement")
    deadline = datetime.fromisoformat(doc["valid_until"])
    if deadline.tzinfo != timezone.utc or deadline.isoformat() != doc["valid_until"] or deadline <= datetime.now(timezone.utc):
        raise ValueError("invalid acknowledgement")
    proof = WriterAcknowledgement(profile_id=doc["profile_id"], host_id=doc["host_id"], backup_id=backup_id, cut_id=cut_id,
                                  roster=frozenset(doc["roster"]), stopped=frozenset(doc["stopped"]),
                                  inventory_complete=True, restart_inhibited=True, valid_until=deadline)
    return backup_id, cut_id, proof


def _cached_receipt(inventory, identifier: str) -> dict:
    receipt = read_receipt(inventory.destination, identifier)
    if receipt["backup_id"] != identifier or receipt["profile_id"] != inventory.profile_id or receipt["host_id"] != inventory.host_id:
        raise ValueError("foreign receipt")
    return receipt


def _list_backups(inventory) -> dict:
    names = []
    with os.scandir(inventory.destination) as entries:
        for entry in entries:
            names.append(entry.name)
            if len(names) > 1000:
                raise ValueError("directory limit")
    receipts, bad = [], 0
    for name in sorted(names):
        if not name.endswith(".receipt.json"):
            continue
        try:
            identifier = _canonical_uuid(name[:-len(".receipt.json")])
            receipt = _cached_receipt(inventory, identifier)
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            bad += 1
            continue
        receipts.append(receipt)
        if len(receipts) > 100:
            raise ValueError("receipt limit")
    return {"receipts": receipts, "receipt_state": "cached", "invalid_receipts": bad}


def _backup_display(result, as_json):
    if as_json:
        print(json.dumps(result, separators=(",", ":"), allow_nan=False))
    else:
        print(json.dumps(result, indent=2, allow_nan=False))


def _backup_dispatch(args) -> int:
    result = {"schema_version": 1, "command": "backup." + args.action,
              "state": "error", "error_code": None, "data": None}
    try:
        identifier = _canonical_uuid(args.id) if args.action == "verify" else None
    except (ValueError, TypeError):
        result.update(state="invalid", error_code="invalid_arguments")
        _backup_display(result, args.json)
        return 2
    try:
        profile = _load_profile(args.profile)
        if args.action == "create":
            backup_id, cut_id, proof = _load_acknowledgement(args.acknowledgement)
        inventory = _load_inventory(profile) if args.action in ("plan", "create") else backup_target_from_profile(profile)
        if args.action == "plan":
            data = {"profile_id": inventory.profile_id, "host_id": inventory.host_id,
                    "sources": [{"logical_id": source.logical_id, "kind": source.kind} for source in inventory.sources],
                    "exclusions": list(inventory.exclusions)}
        elif args.action == "list":
            data = _list_backups(inventory)
        elif args.action == "verify":
            receipt = verify_archive(inventory.destination, identifier)
            if receipt["profile_id"] != inventory.profile_id or receipt["host_id"] != inventory.host_id:
                raise ValueError("foreign receipt")
            data = {"receipt": receipt, "receipt_state": "verified"}
        else:
            from laew.backup.capture import capture_backup
            receipt = capture_backup(inventory, backup_id=backup_id, cut_id=cut_id, writers=proof)
            data = {"receipt": receipt, "receipt_state": "verified"}
        result.update(state="ok", data=data)
        code = 0
    except Exception:
        result["error_code"] = "unavailable_or_invalid"
        code = 1
    _backup_display(result, args.json)
    return code


def _restore_dispatch(args) -> int:
    result = {"schema_version": 1, "command": "restore", "state": "error", "error_code": None, "data": None}
    try:
        identifier = _canonical_uuid(args.id)
        if args.verify_only and (args.apply or args.project_root):
            raise _InvalidArguments
        if args.target and (not args.apply or not Path(args.target).is_absolute()):
            raise _InvalidArguments
        if len(args.project_root) > 32:
            raise _InvalidArguments
    except (ValueError, TypeError, _InvalidArguments):
        result.update(state="invalid", error_code="invalid_arguments")
        _backup_display(result, args.json)
        return 2
    try:
        from laew.backup.restore import restore_backup, verify_restore
        profile = _load_profile(args.profile)
        if args.verify_only:
            receipt = verify_restore(profile, identifier)
            verification = "archive"
        else:
            from laew.backup.recovery_checks import validate_recovery

            workspace = Path(profile["workspace_root"]).resolve()
            vault = Path(profile["vault"]).resolve()
            roots = tuple(Path(raw) for raw in args.project_root)
            for root in roots:
                canonical = root.resolve(strict=True)
                if (not root.is_absolute() or ".." in root.parts or canonical == workspace or
                        not canonical.is_relative_to(workspace) or canonical.is_relative_to(vault) or
                        vault.is_relative_to(canonical)):
                    raise ValueError("invalid project scope")

            receipt = restore_backup(
                profile, identifier, target=Path(args.target),
                validate_staged=lambda staged, manifest: validate_recovery(staged, manifest, project_roots=roots),
            )
            verification = "isolated"
        result.update(state="ok", data={"receipt": receipt, "verification": verification})
        code = 0
    except Exception:
        result["error_code"] = "unavailable_or_invalid"
        code = 1
    _backup_display(result, args.json)
    return code


def dispatch(argv: list[str], *,
             telemetry_root_resolver: Callable[[str | None], str | Path | None] | None = None) -> int:
    """Dispatch an operator command; do not initialize application services.

    Exit 0: operation succeeded; 1: unavailable or invalid state; 2: invalid
    arguments. Resolver failures are reported only as a coarse unavailable state.
    """
    if argv and argv[-1] in ("--help", "-h") and tuple(argv[:-1]) in _HELP:
        print(_HELP[tuple(argv[:-1])])
        return 0
    json_requested = "--json" in argv
    try:
        args = _parser().parse_args(argv)
        if args.command == "backup":
            return _backup_dispatch(args)
        if args.command == "restore":
            return _restore_dispatch(args)
        identifier = str(UUID(args.run_id))
        if identifier != args.run_id:
            raise _InvalidArguments
    except (ValueError, TypeError, _InvalidArguments):
        if argv and argv[0] == "restore":
            _backup_display({"schema_version": 1, "command": "restore", "state": "invalid",
                             "error_code": "invalid_arguments", "data": None}, json_requested)
            return 2
        if argv and argv[0] == "backup":
            action = argv[1] if len(argv) > 1 and argv[1] in ("plan", "list", "verify", "create") else "unknown"
            _backup_display({"schema_version": 1, "command": "backup." + action,
                             "state": "invalid", "error_code": "invalid_arguments", "data": None}, json_requested)
            return 2
        _display(_result("invalid", error_code="invalid_arguments"), json_requested)
        return 2

    if telemetry_root_resolver is None:
        _display(_result("disabled", run_id=identifier, error_code="disabled"), args.json)
        return 1
    try:
        root = telemetry_root_resolver(args.manifest)
        if root is None:
            _display(_result("disabled", run_id=identifier, error_code="disabled"), args.json)
            return 1
        trace = read_run(root, identifier)
    except Exception:
        _display(_result("unknown", run_id=identifier, error_code="unavailable"), args.json)
        return 1

    state = trace["state"]
    if state in ("finished", "active", "interrupted"):
        _display(_result(state, run_id=identifier, events=trace["events"]), args.json)
        return 0
    code = state if state in ("not_found", "corrupt") else "unavailable"
    _display(_result(state if state in ("not_found", "corrupt") else "unknown",
                     run_id=identifier, error_code=code), args.json)
    return 1
