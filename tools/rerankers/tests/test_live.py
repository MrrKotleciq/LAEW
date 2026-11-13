"""Opt-in sequential smoke/lifecycle test. Run ONLY via scripts/run_isolated.py."""
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from client import MODELS, RerankError, RerankerClient, docker_counters, docker_stats

MODEL = os.environ.get("LAEW_RERANKER_LIVE", "")
pytestmark = [pytest.mark.live, pytest.mark.skipif(MODEL not in MODELS, reason="Set LAEW_RERANKER_LIVE to one model")]


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30, check=True)
    return result.stdout.strip()


def wait_ready(client, container, timeout=1800):
    started = time.monotonic()
    next_log = started
    while time.monotonic() - started < timeout:
        state = json.loads(docker("inspect", container))[0]["State"]
        assert state["Running"], f"Startup failed: exit={state['ExitCode']} OOMKilled={state['OOMKilled']}"
        try:
            if client.ready():
                return round(time.monotonic() - started, 3)
        except RerankError:
            if client.model == "mxbai":
                try:
                    startup_failed = client.info()["native"].get("startup_failed", False)
                except RerankError:
                    startup_failed = False
                assert not startup_failed, "Mixedbread initialization failed; inspect its startup log"
        if time.monotonic() >= next_log:
            print(f"Waiting for {container}: {int(time.monotonic() - started)}s", flush=True)
            next_log = time.monotonic() + 30
        time.sleep(3)
    pytest.fail("Readiness timeout; inspect model startup logs and OOMKilled")


def cache_manifest(container, model):
    path = "/models/hf" if model == "mxbai" else "/data"
    script = f"find {path} -type f -name '*.incomplete' -print; find {path} -type f -path '*/blobs/*' -exec stat -c '%n %s %Y' {{}} + | sort"
    return docker("exec", container, "sh", "-c", script)


def test_real_multilingual_and_cache_restart():
    """No ranking quality assertions: verify inference, identity and exact mapping."""
    model = MODEL
    container = f"laew-reranker-{model}-1"
    client = RerankerClient(model)
    baseline = {service: json.loads(docker("inspect", f"laew-{service}-1"))[0]
                for service in ("chromadb", "searxng", "horizon-sufficiency")}
    report = {"model": model, "cases": [], "errors": [], "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    output = os.environ.get("LAEW_RERANKER_REPORT")
    try:
        report["readiness_wait_seconds"] = wait_ready(client, container)
        report["info"] = client.info()
        report["memory_loaded"] = docker_stats(model)
        cases = json.loads((ROOT / "smoke-cases.json").read_text(encoding="utf-8"))
        for case in cases:
            value = {key: case[key] for key in ("query", "documents")}
            before_cpu = docker_counters(model)
            assert before_cpu is not None
            measured_start = time.perf_counter()
            result = client.rerank(value)
            after_cpu = docker_counters(model)
            assert after_cpu is not None
            measured_ms = (time.perf_counter() - measured_start) * 1000
            assert len(result["results"]) == len(value["documents"])
            assert {r["index"] for r in result["results"]} == set(range(len(value["documents"])))
            assert all(r["id"] == value["documents"][r["index"]]["id"] and math.isfinite(r["score"]) for r in result["results"])
            assert result["results"] == sorted(result["results"], key=lambda r: (-r["score"], r["index"]))
            report["cases"].append({"name": case["name"], **result, "stats_after": docker_stats(model),
                                   "cgroup_after": after_cpu,
                                   "cpu_seconds": (after_cpu["usage_usec"] - before_cpu["usage_usec"]) / 1e6,
                                   "cpu_percent_request_window": (after_cpu["usage_usec"] - before_cpu["usage_usec"]) / (measured_ms * 10)})
            print(f"{model} {case['name']}: {result['request_ms']:.1f}ms", flush=True)
        # Native malformed request, and explicit token overflow (within character limit).
        with pytest.raises(RerankError):
            client._request("/v1/rerank" if model == "mxbai" else "/rerank", {})
        long_request = {"query": "initialization", "documents": [{"id": "long", "text": "controller " * 1300}]}
        with pytest.raises(RerankError):
            client.rerank(long_request)
        long_request["truncate"] = True
        report["truncation_check"] = client.rerank(long_request)
        report["cgroup_after_truncation"] = docker_counters(model)
        assert report["truncation_check"]["truncation"]["status"] in {"exact", "unknown"}
        before = cache_manifest(container, model)
        assert ".incomplete" not in before
        report["cache_manifest"] = before.splitlines()
        report["cache_du"] = docker("exec", container, "du", "-sb", "/models/hf" if model == "mxbai" else "/data")
        # Disable network to prove cached startup, then restore the Compose network alias.
        docker("network", "disconnect", "laew_default", container)
        try:
            docker("restart", container)
            started = time.monotonic()
            # Host port is unavailable while disconnected; probe from inside the container.
            health = "/readyz" if model == "mxbai" else "/health"
            port = 8080 if model == "mxbai" else 80
            while time.monotonic() - started < 180:
                state = json.loads(docker("inspect", container))[0]["State"]
                assert state["Running"], f"Offline restart failed: {state}"
                command = (["python", "-c", f"import urllib.request; urllib.request.urlopen('http://127.0.0.1:{port}{health}',timeout=3)"]
                           if model == "mxbai" else ["curl", "-fsS", "--max-time", "3", f"http://127.0.0.1:{port}{health}"])
                probe = subprocess.run(["docker", "exec", container, *command], capture_output=True, timeout=10)
                if probe.returncode == 0:
                    break
                time.sleep(3)
            else:
                pytest.fail("Offline cached restart did not become ready in 180s")
            report["offline_restart_seconds"] = round(time.monotonic() - started, 3)
            report["cache_reused"] = cache_manifest(container, model) == before
            assert report["cache_reused"]
        finally:
            docker("network", "connect", "--alias", f"reranker-{model}", "laew_default", container)
        wait_ready(client, container, timeout=30)
        report["after_restart"] = client.rerank({key: cases[0][key] for key in ("query", "documents")})
        assert report["after_restart"]["results"] == report["cases"][0]["results"]
        report["state_after_restart"] = json.loads(docker("inspect", container))[0]["State"]
        assert not report["state_after_restart"]["OOMKilled"]
        report["success"] = True
    except Exception as error:
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        report["final_state_before_stop"] = json.loads(docker("inspect", container))[0]["State"]
        docker("stop", container)
        report["state_after_stop"] = json.loads(docker("inspect", container))[0]["State"]
        report["other_services_unchanged"] = all(
            (current := json.loads(docker("inspect", f"laew-{name}-1"))[0])["Id"] == old["Id"]
            and current["State"]["StartedAt"] == old["State"]["StartedAt"]
            and current["State"]["Running"] == old["State"]["Running"]
            for name, old in baseline.items())
        clean_stop = report["state_after_stop"]["ExitCode"] == 0 and not report["state_after_stop"]["OOMKilled"]
        report["success"] = bool(report.get("success")) and clean_stop and report["other_services_unchanged"]
        if not clean_stop:
            report["errors"].append({"type": "ShutdownError", "message": "Nonzero exit or OOM on stop"})
        if output:
            Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        assert report["other_services_unchanged"]
        assert clean_stop
