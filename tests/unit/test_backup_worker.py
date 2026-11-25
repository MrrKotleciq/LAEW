"""Standalone worker command admission and Core compatibility."""

import json

from laew.backup_worker import main
from laew.operator_cli import _backup_dispatch, _parser


def test_worker_help_and_forbidden_commands(capsys):
    assert main(['backup', '--help']) == 0
    assert 'backup' in capsys.readouterr().out
    assert main(['backup', 'prune']) == 2
    assert main(['retention', 'apply']) == 2


def test_create_requires_release_proof(capsys):
    assert main(['backup', 'create', '--profile', 'fixture', '--acknowledgement', 'fixture', '--apply']) == 2
    assert 'invalid_arguments' in capsys.readouterr().out


def test_create_unavailable_trust_reports_sanitized_json(monkeypatch, capsys):
    from laew.backup import provenance
    def reject():
        raise ValueError('sensitive local detail')
    monkeypatch.setattr(provenance, 'validate_worker_runtime', reject)
    code = main(['backup', 'create', '--profile', 'fixture', '--acknowledgement', 'fixture',
                 '--provenance', 'fixture', '--apply', '--json'])
    output = capsys.readouterr()
    assert code == 1 and not output.err and 'sensitive local detail' not in output.out
    assert json.loads(output.out)['error_code'] == 'unavailable_or_invalid'


def test_core_status_rejects_empty_worker_options(capsys):
    from laew.operator_cli import dispatch
    assert dispatch(['status', '--backup-worker-status', '', '--json']) == 2
    assert json.loads(capsys.readouterr().out)['error_code'] == 'invalid_arguments'


def test_restore_preflight_runs_for_parsed_apply_option(monkeypatch, capsys):
    from laew.backup import provenance

    checks = []

    def reject():
        checks.append("runtime")
        raise ValueError("untrusted runtime")

    monkeypatch.setattr(provenance, "validate_worker_runtime", reject)
    args = ["restore", "--target", "fixture", "--id", "fixture", "--profile", "fixture", "--app", "--json"]
    assert main(args) == 1 and checks == ["runtime"]
    result = json.loads(capsys.readouterr().out)
    assert result["error_code"] == "unavailable_or_invalid"


def test_busy_observation_does_not_change_core_response(monkeypatch, capsys):
    from laew.backup.fence import FenceBusyError
    import laew.operator_cli as operator
    monkeypatch.setattr(operator, '_load_profile', lambda *_: {})
    monkeypatch.setattr(operator, '_load_acknowledgement', lambda *_: ('id', 'cut', object()))
    monkeypatch.setattr(operator, '_load_inventory', lambda *_: object())
    import laew.backup.capture as capture
    monkeypatch.setattr(capture, 'capture_backup', lambda *a, **k: (_ for _ in ()).throw(FenceBusyError()))
    args = _parser().parse_args(['backup', 'create', '--profile', 'fixture',
                                 '--acknowledgement', 'fixture', '--apply', '--json'])
    observations = []
    assert _backup_dispatch(args, on_result=observations.append) == 1
    assert json.loads(capsys.readouterr().out)['error_code'] == 'unavailable_or_invalid'
    assert observations[0]['error_code'] == 'writer_busy'
