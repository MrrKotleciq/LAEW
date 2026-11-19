import json

import pytest

from laew.operator_cli import dispatch
from laew.telemetry import TelemetrySink


def _json(capsys):
    output = capsys.readouterr()
    assert output.err == ""
    return json.loads(output.out)


def test_show_finished_fixture_with_explicit_resolver(tmp_path, capsys):
    run = TelemetrySink(tmp_path).start_run("cli_chat")
    run.emit("llm.finished", provider="fake", input_tokens=5, input_source="reported", prompt="SECRET")
    run.finish("completed")
    manifests = []
    def resolver(manifest):
        manifests.append(manifest)
        return tmp_path
    assert dispatch(["telemetry", "show", run.run_id, "--manifest", "fixture.yaml", "--json"], telemetry_root_resolver=resolver) == 0
    result = _json(capsys)
    assert manifests == ["fixture.yaml"]
    assert result["schema_version"] == 1
    assert result["command"] == "telemetry.show"
    assert result["state"] == "finished"
    assert result["summary"]["status"] == "completed"
    assert "SECRET" not in str(result)


def test_default_disabled_and_missing_root_is_not_created(tmp_path, capsys):
    identifier = "00000000-0000-4000-8000-000000000000"
    assert dispatch(["telemetry", "show", identifier, "--json"]) == 1
    assert _json(capsys)["state"] == "disabled"
    missing = tmp_path / "absent"
    assert dispatch(["telemetry", "show", identifier, "--json"], telemetry_root_resolver=lambda _: missing) == 1
    assert _json(capsys)["state"] == "not_found"
    assert not missing.exists()


@pytest.mark.parametrize("argv", [
    ["telemetry", "show", "CANARY", "--json"],
    ["telemetry", "show", "--json"],
    ["telemetry", "show", "00000000-0000-4000-8000-000000000000", "--secret-CANARY", "--json"],
    ["telemetry", "CANARY", "--json"],
])
def test_invalid_arguments_are_json_and_do_not_call_resolver(argv, capsys):
    def resolver(_):
        raise AssertionError("resolver called")
    assert dispatch(argv, telemetry_root_resolver=resolver) == 2
    result = _json(capsys)
    assert result["error_code"] == "invalid_arguments"
    assert result["run_id"] is None
    assert "CANARY" not in str(result)


def test_resolver_errors_and_corrupt_records_do_not_disclose_data(tmp_path, capsys):
    identifier = "00000000-0000-4000-8000-000000000000"
    def resolver(_):
        raise RuntimeError("SECRET /private/path")
    assert dispatch(["telemetry", "show", identifier, "--json"], telemetry_root_resolver=resolver) == 1
    assert "SECRET" not in str(_json(capsys))
    run = TelemetrySink(tmp_path).start_run("cli_chat")
    run.finish("completed")
    (tmp_path / (run.run_id + ".jsonl")).write_text('{"SECRET":"CANARY"}\n')
    assert dispatch(["telemetry", "show", run.run_id, "--json"], telemetry_root_resolver=lambda _: tmp_path) == 1
    result = _json(capsys)
    assert result["state"] == "corrupt"
    assert "SECRET" not in str(result)


def test_interrupted_and_human_output(tmp_path, capsys):
    run = TelemetrySink(tmp_path).start_run("workbench")
    run._close()
    assert dispatch(["telemetry", "show", run.run_id], telemetry_root_resolver=lambda _: tmp_path) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "interrupted" in captured.out


@pytest.mark.parametrize("args, expected", [
    (["telemetry", "--help"], "{show}"),
    (["telemetry", "show", "--help"], "RUN_ID"),
])
def test_operator_telemetry_help(args, expected, capsys):
    assert dispatch(args) == 0
    assert expected in capsys.readouterr().out
