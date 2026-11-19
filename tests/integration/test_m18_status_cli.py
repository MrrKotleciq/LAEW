"""Exercise the normal operator entry point against a disposable manifest."""

import json
from pathlib import Path
import subprocess
import sys


def test_status_cli_uses_validated_metadata_and_stable_exit_codes(tmp_path):
    manifest = tmp_path / "fixture.yaml"
    source = Path(__file__).resolve().parents[2] / "manifests" / "SYSTEM_MANIFEST.yaml"
    manifest.write_bytes(source.read_bytes())
    before = {path.name for path in tmp_path.iterdir()}

    def status(*args):
        result = subprocess.run([sys.executable, "-m", "laew.cli", "status", "--json", *args],
                                capture_output=True, text=True, timeout=10)
        assert result.stderr == ""
        return result.returncode, json.loads(result.stdout)

    code, data = status("--manifest", str(manifest))
    assert code == 1
    assert data["schema_version"] == 1
    assert data["overall"] == "degraded"
    provider = next(check for check in data["checks"] if check["component"] == "provider")
    assert provider["state"] == "unknown" and provider["reason"] == "not_probed"
    assert provider["required"] is True
    assert {path.name for path in tmp_path.iterdir()} == before

    code, data = status("--manifest", str(tmp_path / "private-name"))
    assert code == 2 and data["overall"] == "unavailable"
    assert "private-name" not in str(data)

    code, data = status("--rag-max-age-seconds", "invalid-secret")
    assert code == 2 and data["error_code"] == "invalid_arguments"
    assert "invalid-secret" not in str(data)
