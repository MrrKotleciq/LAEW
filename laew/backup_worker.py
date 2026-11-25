"""Standalone, explicitly supervised backup and isolated recovery entry point."""

import sys
from pathlib import Path

from laew.operator_cli import _InvalidArguments, _backup_dispatch, _backup_display, _bounded_file, _parser, dispatch


def managed_create(argv):
    import argparse
    from laew.operator_cli import _load_inventory, _load_profile
    from laew.backup.capture import capture_backup
    from laew.backup.managed import ManagedCut
    from laew.backup.policy import admission
    from laew.backup.provenance import ReleaseProof, validate_worker_media, validate_worker_runtime

    parser = argparse.ArgumentParser(prog="laew-backup-worker managed-create", allow_abbrev=False)
    for name in ("profile", "gate", "provenance"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--apply", action="store_true", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        validate_worker_runtime()
        validate_worker_media(args.profile)
        with admission(args.profile, operation="capture", managed=True):
            inventory = _load_inventory(_load_profile(str(args.profile)))
            cut = ManagedCut(args.gate, args.profile, inventory, ReleaseProof(args.provenance, args.profile))
            receipt = capture_backup(inventory, backup_id=cut.ack.backup_id, cut_id=cut.ack.cut_id,
                                     writers=cut.ack, provenance_check=cut)
    except (ValueError, TypeError, RuntimeError, OSError):
        return _failure(["backup", "create", *argv], False)
    _backup_display({"schema_version": 1, "command": "backup.create", "state": "ok", "error_code": None,
                     "data": {"receipt": receipt, "receipt_state": "verified"}}, args.json)
    return 0


def _failure(argv, invalid):
    command = ('backup.' + (argv[1] if len(argv) > 1 and argv[1] in
                           ('plan', 'list', 'verify', 'create') else 'unknown')
               if argv and argv[0] == 'backup' else 'restore')
    result = {'schema_version': 1, 'command': command,
              'state': 'invalid' if invalid else 'error',
              'error_code': 'invalid_arguments' if invalid else 'unavailable_or_invalid', 'data': None}
    _backup_display(result, '--json' in argv)
    return 2 if invalid else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in ([], ['--help'], ['-h']):
        print('usage: laew-backup-worker {backup,restore,control,managed-create} ...')
        return 0
    if argv[0] == "control":
        from laew.backup.controls import main as control
        return control(argv[1:])
    if argv[0] == "managed-create":
        return managed_create(argv[1:])
    allowed = bool(argv and (argv[0] == 'restore' or
                            (argv[0] == 'backup' and (len(argv) == 1 or
                             argv[1] in ('plan', 'list', 'verify', 'create', '--help', '-h')))))
    if not allowed:
        return _failure(argv, True)
    original_argv = list(argv)
    try:
        if argv[-1:] in (['--help'], ['-h']):
            if argv[:-1] == ['backup']:
                print('usage: laew-backup-worker backup {plan,list,verify,create} ...')
                return 0
            if argv[:-1] == ['backup', 'create']:
                print('usage: laew-backup-worker backup create --profile PROFILE '
                      '--acknowledgement ABS --provenance ABS --apply [--status-file ABS] [--json]')
                return 0
            if argv[:-1] == ['backup', 'verify']:
                print('usage: laew-backup-worker backup verify --profile PROFILE --id ID '
                      '[--status-file ABS] [--json]')
                return 0
            return dispatch(argv)
        status_path = provenance_path = None
        for option in ('--status-file', '--provenance'):
            if option in argv:
                index = argv.index(option)
                if argv.count(option) != 1 or index + 1 >= len(argv):
                    raise ValueError('invalid worker option')
                value = argv[index + 1]
                if not value or value.startswith('--'):
                    raise ValueError('invalid worker option')
                del argv[index:index + 2]
                if option == '--status-file':
                    status_path = value
                else:
                    provenance_path = value
        create = argv[:2] == ['backup', 'create']
        if status_path and argv[:2] not in (['backup', 'create'], ['backup', 'verify']):
            raise ValueError('unsupported status operation')
        if bool(provenance_path) != create:
            raise ValueError('create requires provenance')
        args = _parser().parse_args(argv)
        if not create and not status_path and not (args.command == 'restore' and args.apply):
            return dispatch(argv)
    except (ValueError, TypeError, _InvalidArguments):
        return _failure(original_argv, True)
    try:
        provenance = None
        if create or (args.command == 'restore' and args.apply):
            from laew.backup.provenance import ReleaseProof, validate_worker_media, validate_worker_runtime
            validate_worker_runtime()
            if create:
                _bounded_file(Path(args.acknowledgement), 65536, private=True)
                provenance = ReleaseProof(provenance_path, args.profile)
            else:
                validate_worker_media(args.profile)
        if args.command == 'restore':
            return dispatch(argv)
        callback = lambda observer: _backup_dispatch(args, on_result=observer,
                                                     provenance_check=provenance)
        if status_path:
            from laew.backup.health import run_with_status
            operation = 'capture' if args.action == 'create' else 'verify'
            return run_with_status(status_path, args.profile, operation, callback)
        return callback(None)
    except Exception:
        return _failure(original_argv, False)


if __name__ == '__main__':
    sys.exit(main())
