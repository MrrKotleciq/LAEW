"""Run a disposable M17 validation against a dedicated local Chroma server.

The script never opens the production database or vault. It leaves the test
workspace and JSON report under the Git-ignored runtime directory for review.
Existing chat and embedding servers are used read-only for inference.
"""

import argparse
import copy
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from http.server import ThreadingHTTPServer

import requests
import yaml

from laew.manifest import load_manifest
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool
from laew.web import WorkspaceService, make_handler

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    if port in {8000, 8080, 8081, 8765}:
        raise RuntimeError("Refusing to use a production service port.")
    return port


def wait_http(url, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Test Chroma process exited before startup.")
        try:
            if requests.get(url, timeout=1).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(.2)
    raise TimeoutError("Test Chroma did not start.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Create and run an isolated validation workspace")
    parser.add_argument("--model", action="store_true", help="Also exercise the configured live chat model")
    parser.add_argument("--hold", type=int, default=0, help="Keep the isolated Workbench open for this many seconds")
    parser.add_argument("--first-only", action="store_true", help="Capture only the embedding-failure agent scenario")
    args = parser.parse_args()
    if not args.run:
        parser.error("Pass --run to create the isolated test workspace.")
    base = ROOT / "runtime" / ("m17-validation-" + uuid.uuid4().hex[:12])
    base.mkdir(parents=True, exist_ok=False)
    projects = base / "Projects"; projects.mkdir()
    a = projects / "Project-A"; a.mkdir()
    external = base / "External" / "Project-B"; external.mkdir(parents=True)
    vault = base / "Knowledge"; vault.mkdir()
    locks = base / "locks"; locks.mkdir()
    for key in ("TEMP", "TMP", "TMPDIR"):
        os.environ[key] = str(locks)
    tempfile.tempdir = str(locks)
    for key in ("LAEW_BASE_URL", "LAEW_TIMEOUT", "LAEW_WORKSPACE_ROOT"):
        os.environ.pop(key, None)
    for project, code in ((a, "M17-PROJECT-A-7319"), (external, "M17-PROJECT-B-4826")):
        (project / "docs").mkdir()
        (project / "docs" / "verify.md").write_text(f"# Verification\nProject verification code: {code}\n", encoding="utf-8")
    note = vault / "global.md"
    note.write_text("# Shared verification\nGlobal verification code: M17-GLOBAL-VERIFY-9381\n", encoding="utf-8")
    chroma_port, web_port = free_port(), free_port()
    while web_port == chroma_port:
        web_port = free_port()
    manifest = load_manifest(ROOT / "manifests" / "SYSTEM_MANIFEST.yaml")
    manifest["rag"]["vector_store"].update({"enabled": True, "host": "127.0.0.1", "port": chroma_port,
                                             "global_collection": "m17_global_test"})
    manifest["rag"]["project_sources"]["allowlist"] = ["docs/*.md"]
    manifest_path = base / "test-manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    # Fail closed before starting any service or building a RAG client.
    cfg = manifest["rag"]["vector_store"]
    if cfg["host"] != "127.0.0.1" or cfg["port"] in (8000, 8080, 8081, 8765) or cfg["global_collection"] == "laew_global":
        raise RuntimeError("Unsafe test configuration; refusing to run.")
    chroma_exe = Path(sys.executable).with_name("chroma.exe" if os.name == "nt" else "chroma")
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    log = (base / "chroma.log").open("w", encoding="utf-8")
    child = subprocess.Popen([str(chroma_exe), "run", "--host", "127.0.0.1", "--port", str(chroma_port),
                              "--path", str(base / "chroma-data")], stdout=log, stderr=subprocess.STDOUT, **kwargs)
    service = server = None
    report = {"workspace": str(base), "project_a": str(a), "project_b": str(external),
              "knowledge": str(vault), "chroma_port": chroma_port, "workbench_port": web_port, "checks": {}}
    try:
        wait_http(f"http://127.0.0.1:{chroma_port}/api/v2/heartbeat", child)
        tools = [build_rag_tool(manifest, project_root=p, projects_root=projects, knowledge_root=vault) for p in (a, external)]
        for index, tool in enumerate(tools):
            kb = tool._pipeline.knowledge_base
            assert kb.project_store.collection_name != "laew_project_88db54302bfb3ba82bfe009c0c1072f0"
            report["checks"][f"sync_project_{index}"] = synchronize_scope(kb, "project")
        report["checks"]["sync_global"] = synchronize_scope(tools[0]._pipeline.knowledge_base, "global")
        kb = tools[0]._pipeline.knowledge_base
        calls = []
        old = kb.embedding_service.embed_batch
        def counted(texts):
            calls.append(len(texts)); return old(texts)
        kb.embedding_service.embed_batch = counted
        report["checks"]["unchanged"] = synchronize_scope(kb, "project")
        report["checks"]["unchanged_embedding_chunks"] = sum(calls)
        assert not calls, "Unchanged project unexpectedly re-embedded."
        for index, (tool, code) in enumerate(zip(tools, ("M17-PROJECT-A-7319", "M17-PROJECT-B-4826"))):
            result = tool.call("query", query=code, scope="project")
            assert result.success and code in result.data.get("context", "")
            other = "M17-PROJECT-B-4826" if index == 0 else "M17-PROJECT-A-7319"
            assert other not in result.data.get("context", "")
            report["checks"][f"retrieve_project_{index}"] = result.data.get("sources")
            global_result = tool.call("query", query="M17-GLOBAL-VERIFY-9381", scope="global")
            assert global_result.success and "M17-GLOBAL-VERIFY-9381" in global_result.data.get("context", "")
        import chromadb
        db = chromadb.HttpClient(host="127.0.0.1", port=chroma_port)
        collections = [tool._pipeline.knowledge_base.project_store.collection_name for tool in tools]
        assert len(set(collections)) == 2
        report["checks"]["collections"] = {name: db.get_collection(name).count() for name in collections + ["m17_global_test"]}
        for name in collections:
            metadata = db.get_collection(name).get(include=["metadatas"])["metadatas"]
            assert all(item.get("source") == "project" and "M17-GLOBAL-VERIFY-9381" not in item.get("text", "") for item in metadata)
        global_metadata = db.get_collection("m17_global_test").get(include=["metadatas"])["metadatas"]
        assert all(item.get("source") == "global" for item in global_metadata)
        first_doc = a / "docs" / "verify.md"
        first_doc.write_text("# Verification\nProject verification code: M17-PROJECT-A-UPDATED\n", encoding="utf-8")
        def fail_embedding(_texts):
            raise RuntimeError("Simulated embedding service outage")
        kb.embedding_service.embed_batch = fail_embedding
        try:
            synchronize_scope(kb, "project")
            raise AssertionError("Embedding failure did not fail synchronization.")
        except AssertionError:
            raise
        except RuntimeError:
            pass
        blocked = tools[0].call("query", query="M17-PROJECT-A-7319", scope="project")
        healthy = tools[0].call("query", query="M17-GLOBAL-VERIFY-9381", scope="global")
        assert not blocked.success and healthy.success
        report["checks"]["embedding_failure"] = {"project_blocked": not blocked.success, "global_healthy": healthy.success}
        kb.embedding_service.embed_batch = counted
        first_doc.write_text("# Verification\nProject verification code: M17-PROJECT-A-UPDATED\n", encoding="utf-8")
        calls.clear(); report["checks"]["project_update"] = synchronize_scope(kb, "project")
        report["checks"]["project_update_embedding_chunks"] = sum(calls)
        records = kb.project_store.sync_records("project")
        assert any("M17-PROJECT-A-UPDATED" in r.text for r in records)
        assert all("M17-PROJECT-A-7319" not in r.text for r in records)
        assert any("M17-PROJECT-B-4826" in r.text for r in tools[1]._pipeline.knowledge_base.project_store.sync_records("project"))
        first_doc.unlink(); report["checks"]["project_delete"] = synchronize_scope(kb, "project")
        assert not kb.project_store.sync_records("project")
        first_doc.write_text("# Verification\nProject verification code: M17-PROJECT-A-7319\n", encoding="utf-8")
        report["checks"]["project_restore"] = synchronize_scope(kb, "project")
        note.write_text("# Shared verification\nGlobal verification code: M17-GLOBAL-UPDATED\n", encoding="utf-8")
        report["checks"]["global_update"] = synchronize_scope(kb, "global")
        assert any("M17-GLOBAL-UPDATED" in r.text for r in kb.global_store.sync_records("global"))
        note.unlink(); report["checks"]["global_delete"] = synchronize_scope(kb, "global")
        assert not kb.global_store.sync_records("global")
        note.write_text("# Shared verification\nGlobal verification code: M17-GLOBAL-VERIFY-9381\n", encoding="utf-8")
        report["checks"]["global_restore"] = synchronize_scope(kb, "global")
        service = WorkspaceService(manifest_path, a, projects, base, registered_projects=[external])
        server = ThreadingHTTPServer(("127.0.0.1", web_port), make_handler(service))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        service.start_sync()
        api = f"http://127.0.0.1:{web_port}"
        (base / "environment.json").write_text(json.dumps({"workbench": api, "chroma_port": chroma_port,
            "workspace": str(base)}, indent=2), encoding="utf-8")
        print(f"ISOLATED_WORKBENCH={api} WORKSPACE={base}", flush=True)
        response = requests.get(api + "/api/projects", timeout=10); response.raise_for_status()
        listed = response.json(); by_name = {p["name"]: p for p in listed["projects"]}
        assert {"Project-A", "Project-B"} <= set(by_name)
        response = requests.post(api + "/api/project", json={"project_id": by_name["Project-B"]["id"]}, timeout=30)
        response.raise_for_status()
        report["checks"]["workbench_switch"] = response.json()["project"]["path"]
        if args.model:
            cases = []
            report["checks"]["live_agent_cases"] = []
            for name, prompt in cases:
                project_id = by_name[name]["id"]
                response = requests.post(api + "/api/project", json={"project_id": project_id}, timeout=30)
                response.raise_for_status()
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    status = requests.get(api + "/api/rag", timeout=10).json()
                    if all(status.get(scope, {}).get("state") == "successfully synchronized" for scope in ("project", "global")):
                        break
                    time.sleep(.2)
                response = requests.post(api + "/api/chat", json={"message": prompt, "provider": "manifest",
                    "project_id": project_id, "session_id": uuid.uuid4().hex}, timeout=(10, 240), stream=True)
                response.raise_for_status()
                events = [json.loads(line.decode("utf-8")) for line in response.iter_lines() if line]
                done = next((event for event in events if event.get("type") == "done"), {})
                steps = [event.get("step", {}) for event in events if event.get("type") == "step"]
                wanted = (["M17-GLOBAL-VERIFY-9381"] if "scope=global" in prompt else
                          ["M17-PROJECT-A-7319", "M17-GLOBAL-VERIFY-9381"] if "scope=hybrid" in prompt else
                          ["M17-PROJECT-A-7319" if name == "Project-A" else "M17-PROJECT-B-4826"])
                report["checks"]["live_agent_cases"].append({"project": name, "prompt": prompt, "events": events,
                    "rag_tool_succeeded": any(s.get("tool") == "RagTool" and s.get("success") for s in steps),
                    "expected_codes_in_answer": all(code in done.get("response", "") for code in wanted)})
        if args.model:
            from laew.rag.sync import sync_status, _process_lock
            from laew.llm.llamacpp import LlamaCppProvider
            original_request = LlamaCppProvider._request
            raw_streams = []
            def capture_request(provider, *args, **kwargs):
                response = original_request(provider, *args, **kwargs)
                if kwargs.get("stream"):
                    original_lines = response.iter_lines
                    def capture_lines(*line_args, **line_kwargs):
                        lines = []
                        raw_streams.append(lines)
                        for line in original_lines(*line_args, **line_kwargs):
                            lines.append(line if isinstance(line, bytes) else line.encode("utf-8"))
                            yield line
                    response.iter_lines = capture_lines
                return response
            LlamaCppProvider._request = capture_request
            response = requests.post(api + "/api/project", json={"project_id": by_name["Project-A"]["id"]}, timeout=30)
            response.raise_for_status()
            service.close()
            synchronize_scope(kb, "project"); synchronize_scope(kb, "global")
            def chat(label, prompt):
                service._reset_runtime()
                start_stream = len(raw_streams)
                response = requests.post(api + "/api/chat", json={"message": prompt, "provider": "manifest", "project_id": by_name["Project-A"]["id"], "session_id": uuid.uuid4().hex}, timeout=(10,240), stream=True)
                response.raise_for_status()
                events = [json.loads(line.decode("utf-8")) for line in response.iter_lines() if line]
                report["checks"][label] = {"sync_project": sync_status(kb,"project"), "sync_global": sync_status(kb,"global"), "events": events}
                raw = b"\n".join(line for stream in raw_streams[start_stream:] for line in stream)
                (base / (label + "-provider-sse.bin")).write_bytes(raw)
                report["checks"][label]["provider_utf8_replacement_bytes"] = raw.count(b"\xef\xbf\xbd")
                (base / "report-progress.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            prompt = "Use RagTool scope=project to find the exact project verification code and cite its source. If retrieval fails, report the failure honestly."
            first_doc.write_text("# Changed\nNew project verification code: M17-NEW-4321\n", encoding="utf-8")
            kb.embedding_service.embed_batch = fail_embedding
            try: synchronize_scope(kb, "project")
            except RuntimeError: pass
            kb.embedding_service.embed_batch = old
            report["checks"]["failure_direct_project"] = str(tools[0].call("query", query="verification code", scope="project"))
            report["checks"]["failure_direct_global"] = str(tools[0].call("query", query="verification code", scope="global"))
            chat("agent_embedding_outage", prompt)
            if not args.first_only:
                synchronize_scope(kb, "project")
                child.terminate(); child.wait(timeout=10)
                chat("agent_chroma_outage", prompt)
                child = subprocess.Popen([str(chroma_exe), "run", "--host", "127.0.0.1", "--port", str(chroma_port), "--path", str(base / "chroma-data")], stdout=log, stderr=subprocess.STDOUT, **kwargs)
                wait_http(f"http://127.0.0.1:{chroma_port}/api/v2/heartbeat", child)
                synchronize_scope(kb, "project")
                chat("agent_chroma_recovered", prompt)
                lock = _process_lock(kb, "project").acquire()
                try: lock.write_state({"state":"incomplete", "generation":"simulated-interrupted"})
                finally: lock.release()
                chat("agent_incomplete", prompt)
                synchronize_scope(kb, "project")
                chat("agent_incomplete_recovered", prompt)
            first_doc.write_text("# Verification\nProject verification code: M17-PROJECT-A-7319\n", encoding="utf-8")
            synchronize_scope(kb, "project")
        if args.hold:
            time.sleep(min(args.hold, 300))
        server.shutdown(); server.server_close(); server = None
        service.close(); service = None
        restart_script = r'''
import json,sys
from pathlib import Path
from laew.manifest import load_manifest
from laew.runtime import build_rag_tool
from laew.rag.sync import synchronize_scope,freshness_error
manifest=load_manifest(Path(sys.argv[1]))
kb=build_rag_tool(manifest,project_root=Path(sys.argv[2]),projects_root=Path(sys.argv[3]),knowledge_root=Path(sys.argv[4]))._pipeline.knowledge_base
before=freshness_error(kb,"project")
calls=[]; old=kb.embedding_service.embed_batch
def track(texts): calls.append(len(texts)); return old(texts)
kb.embedding_service.embed_batch=track
result=synchronize_scope(kb,"project")
print(json.dumps({"blocked_before_sync":bool(before),"sync":result,"embedding_chunks":sum(calls)}))
'''
        restarted = subprocess.run([sys.executable, "-c", restart_script, str(manifest_path), str(a), str(projects), str(vault)],
                                   capture_output=True, text=True, timeout=60, **kwargs)
        if restarted.returncode:
            raise RuntimeError(f"Restart validation failed: {restarted.stderr[-1000:]}")
        report["checks"]["process_restart"] = json.loads(restarted.stdout)
        assert report["checks"]["process_restart"]["blocked_before_sync"]
        assert report["checks"]["process_restart"]["embedding_chunks"] == 0
        unavailable_manifest = copy.deepcopy(manifest)
        unavailable_port = free_port()
        unavailable_manifest["agent"]["llm"]["providers"][0].update({"host": "127.0.0.1", "port": unavailable_port})
        unavailable_path = base / "unavailable-llm-manifest.yaml"
        unavailable_path.write_text(yaml.safe_dump(unavailable_manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
        offline_service = WorkspaceService(unavailable_path, a, projects, base)
        offline_status = offline_service.status()
        assert not offline_status["available"] and offline_status["error"]
        report["checks"]["unavailable_llm"] = {"available": offline_status["available"], "error": offline_status["error"]}
        synchronize_scope(kb, "project")
        child.terminate(); child.wait(timeout=10)
        try:
            synchronize_scope(kb, "project")
            raise AssertionError("Synchronization unexpectedly succeeded while test Chroma was stopped.")
        except AssertionError:
            raise
        except Exception as exc:
            report["checks"]["chroma_outage"] = type(exc).__name__
        blocked = tools[0].call("query", query="M17-PROJECT-A-7319", scope="project")
        assert not blocked.success
        report["checks"]["outage_retrieval_blocked"] = blocked.error_code
        child = subprocess.Popen([str(chroma_exe), "run", "--host", "127.0.0.1", "--port", str(chroma_port),
                                  "--path", str(base / "chroma-data")], stdout=log, stderr=subprocess.STDOUT, **kwargs)
        wait_http(f"http://127.0.0.1:{chroma_port}/api/v2/heartbeat", child)
        report["checks"]["chroma_recovery_sync"] = synchronize_scope(kb, "project")
        recovered = tools[0].call("query", query="M17-PROJECT-A-7319", scope="project")
        assert recovered.success and "M17-PROJECT-A-7319" in recovered.data.get("context", "")
        report["checks"]["chroma_recovery_sources"] = recovered.data.get("sources")
        report["result"] = "completed"
    except Exception as exc:
        report["result"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if server:
            server.shutdown(); server.server_close()
        if service:
            service.close()
        child.terminate()
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill(); child.wait()
        log.close()
        (base / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
