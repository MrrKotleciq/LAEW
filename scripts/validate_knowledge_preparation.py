"""Validate approved-scope preparation in a disposable HTTP Chroma database.

Only inference reaches existing model services. The production knowledge vault
and database are never opened. The real academic project is read, not modified.
Candidate global notes, including profile drafts, are copied to an isolated vault.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

import requests
import yaml

from laew.manifest import load_manifest
from laew.project_config import load_project_settings
from laew.rag.identity import project_collection_name
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool
from laew.web import WorkspaceService, make_handler
from scripts.validate_m17 import free_port, wait_http


ROOT = Path(__file__).resolve().parents[1]


def layout_prefixes(vault):
    """Support both the historical preparation fixture and the reorganized vault."""
    names = {p.name for p in Path(vault).iterdir() if p.is_dir()}
    return ("topics" if "topics" in names else "Knowledge",
            "research" if "research" in names else "Research",
            "decisions" if "decisions" in names else "Decisions")


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--model", action="store_true")
    parser.add_argument("--project", type=Path, default=ROOT.parent / "Studia")
    parser.add_argument("--candidates", type=Path,
                        default=ROOT / "runtime/knowledge-preparation-2026-10-29/Global-Knowledge")
    args = parser.parse_args()
    if not args.run:
        parser.error("Pass --run to create an isolated validation workspace.")
    project = args.project.resolve(strict=True)
    candidates = args.candidates.resolve(strict=True)
    if not project.is_dir() or not candidates.is_dir():
        parser.error("Project and candidate paths must be directories.")
    # Copy inputs before opening any database; never point the test at a real vault.
    base = ROOT / "runtime" / ("knowledge-validation-" + uuid.uuid4().hex[:12])
    base.mkdir(parents=True)
    vault = base / "Knowledge"
    shutil.copytree(candidates, vault)
    projects = base / "Projects"
    fixture = projects / "Academic-Fixture"
    other = projects / "Other-Fixture"
    fixture.mkdir(parents=True)
    other.mkdir()
    shutil.copy(project / ".laew-project.json", fixture / ".laew-project.json")
    fixtures = {
        "docs/semestr-01/control/note.md": "PID fixture: controller experiment label STUDY-CONTROL-ONLY.",
        "docs/semestr-01/algebra/note.md": "Matrix fixture: matrix multiplication label STUDY-ALGEBRA-ONLY.",
        "docs/semestr-02/digital/note.md": "Logic fixture: digital gate label STUDY-DIGITAL-ONLY.",
    }
    for relative, body in fixtures.items():
        note = fixture / relative
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("---\nname: Fictional test only\ntype: docs\nscope: project\n"
                        "tags: [fixture]\nsemester: 1\n---\n# Fictional fixture\n"
                        + body + "\n[[docs/semestr-01/algebra/note]]\n", encoding="utf-8")
    (other / "README.md").write_text("PID OTHER-PROJECT-ONLY fixture", encoding="utf-8")
    project_before = snapshot(project)
    candidate_before = snapshot(candidates)
    locks = base / "locks"
    locks.mkdir()
    for key in ("TEMP", "TMP", "TMPDIR"):
        os.environ[key] = str(locks)
    tempfile.tempdir = str(locks)
    for key in ("LAEW_BASE_URL", "LAEW_TIMEOUT", "LAEW_WORKSPACE_ROOT"):
        os.environ.pop(key, None)
    chroma_port, web_port = free_port(), free_port()
    while chroma_port == web_port:
        web_port = free_port()
    manifest = load_manifest(ROOT / "manifests/SYSTEM_MANIFEST.yaml")
    manifest["rag"]["vector_store"].update(
        {"enabled": True, "host": "127.0.0.1", "port": chroma_port,
         "global_collection": "knowledge_preparation_test"})
    cfg = manifest["rag"]["vector_store"]
    if cfg["port"] in {8000, 8080, 8081, 8765} or cfg["global_collection"] == "laew_global":
        raise RuntimeError("Refusing production service configuration.")
    manifest_path = base / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    chroma_exe = Path(sys.executable).with_name("chroma.exe" if os.name == "nt" else "chroma")
    report = {"workspace": str(base), "project": str(project), "project_settings": load_project_settings(project),
              "production_vault_modified": False, "production_database_opened": False,
              "candidate_hashes": candidate_before, "checks": {}, "model_cases": []}
    checks = report["checks"]
    child = server = service = None
    log = (base / "chroma.log").open("w", encoding="utf-8")
    print(f"VALIDATION_WORKSPACE={base}", flush=True)
    try:
        child = subprocess.Popen([str(chroma_exe), "run", "--host", "127.0.0.1", "--port", str(chroma_port),
                                  "--path", str(base / "chroma-data")], stdout=log, stderr=subprocess.STDOUT,
                                 **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        wait_http(f"http://127.0.0.1:{chroma_port}/api/v2/heartbeat", child)
        tools = [build_rag_tool(manifest, project_root=p, projects_root=projects, knowledge_root=vault)
                 for p in (project, fixture, other)]
        for i, tool in enumerate(tools):
            checks[f"project_sync_{i}"] = synchronize_scope(tool._pipeline.knowledge_base, "project")
        kb = tools[0]._pipeline.knowledge_base
        checks["global_sync"] = synchronize_scope(kb, "global")
        checks["collections"] = [project_collection_name(p) for p in (project, fixture, other)]
        assert len(set(checks["collections"])) == 3
        records = kb.global_store.sync_records("global")
        checks["global_records"] = [{"id": r.chunk_id, "source": r.source,
                                     "path": r.file_path, "metadata": r.metadata} for r in records]
        assert {r.file_path.replace("\\", "/") for r in records} == {
            p.relative_to(vault).as_posix() for p in vault.rglob("*.md")
            if kb._source_selected(p.relative_to(vault).as_posix(), "global")
            and not any(part.startswith(".") for part in p.relative_to(vault).parts)}
        calls = []
        embed = kb.embedding_service.embed_batch
        def counted(texts):
            calls.append(len(texts))
            return embed(texts)
        kb.embedding_service.embed_batch = counted
        checks["global_unchanged"] = synchronize_scope(kb, "global")
        checks["unchanged_embedding_chunks"] = sum(calls)
        assert not calls
        topics, research, decisions = layout_prefixes(vault)
        queries = [
            ("How should document fingerprints include chunk settings and embedding identity?", f"{topics}/ai/incremental-indexing.md"),
            ("How should an assistant divide its context budget and reserve room for an answer?", f"{topics}/ai/context-budgeting.md"),
            ("Why must tool authorization and filesystem path boundaries be enforced below the model?", f"{topics}/security/tool-boundaries.md"),
            ("How can I distinguish correct indexing, relevant retrieval, provenance and model interpretation?", f"{research}/retrieval-evaluation.md"),
            ("Where should project measurements, reusable methods and approved user preferences belong?", f"{decisions}/memory-boundaries.md"),
            ("W jakim języku użytkownik chce komunikacji i dokumentacji technicznej LAEW?", "profile/preferences.md"),
        ]
        checks["topic_queries"] = []
        for query, expected in queries:
            result = tools[0].call("query", query=query, scope="global", max_results=3)
            found = result.success and "@knowledge/" + expected in result.data.get("sources", [])
            checks["topic_queries"].append({"query": query, "expected": expected, "pass": found,
                                            "result": result.data, "error": result.error_message})
            assert found, f"Expected source missing: {expected}"
        for relative, body in fixtures.items():
            result = tools[1].call("query", query=body.split(":")[0], scope="project", max_results=3)
            assert result.success and "@project/" + relative in result.data["sources"]
            assert "OTHER-PROJECT-ONLY" not in result.data["context"]
        checks["nested_sources"] = [r.file_path for r in tools[1]._pipeline.knowledge_base.project_store.sync_records("project")]
        hybrid = tools[1].call("query", query="PID fixture controller and document fingerprint synchronization", scope="hybrid", max_results=3)
        checks["hybrid"] = hybrid.data
        assert hybrid.success and any(s.startswith("@project/") for s in hybrid.data["sources"])
        assert any(s.startswith("@knowledge/") for s in hybrid.data["sources"])
        changed = vault / topics / "ai/incremental-indexing.md"
        original = changed.read_text(encoding="utf-8")
        changed.write_text(original + "\nISOLATED-UPDATE-ONLY\n", encoding="utf-8")
        checks["isolated_global_update"] = synchronize_scope(kb, "global")
        assert any("ISOLATED-UPDATE-ONLY" in r.text for r in kb.global_store.sync_records("global"))
        changed.write_text(original, encoding="utf-8")
        synchronize_scope(kb, "global")
        assert not any("ISOLATED-UPDATE-ONLY" in r.text for r in kb.global_store.sync_records("global"))
        service = WorkspaceService(manifest_path, project, projects, base, registered_projects=[project])
        server = ThreadingHTTPServer(("127.0.0.1", web_port), make_handler(service))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        api = f"http://127.0.0.1:{web_port}"
        listed = requests.get(api + "/api/projects", timeout=10).json()
        by_name = {p["name"]: p for p in listed["projects"]}
        assert "Studia" in by_name
        project_id = by_name["Studia"]["id"]
        response = requests.post(api + "/api/project", json={"project_id": project_id}, timeout=10)
        response.raise_for_status()
        checks["workbench_project_selection"] = response.json()
        checks["documentation_language"] = service.project_settings()[1]["documentation_language"]
        assert checks["documentation_language"] == "pl"
        if args.model:
            cases = [
                ("Studia", "Użyj RagTool scope=project. Jakie pliki Markdown są indeksowane w projekcie Studia, czy PDF jest przeszukiwalny i jaki jest język dokumentacji? Odpowiedz krótko po polsku z dokładnym źródłem. Nie wywołuj innych narzędzi.", ["@project/README.md"]),
                ("Academic-Fixture", "Use RagTool scope=hybrid to retrieve the fictional PID controller experiment label and the shared method for incremental document indexing. Explain in Polish how to check that an unchanged sync avoids unnecessary embeddings. Cite both exact project and global sources. Do not call other tools.", ["@project/docs/semestr-01/control/note.md", f"@knowledge/{topics}/ai/incremental-indexing.md"]),
            ]
            for name, prompt, wanted in cases:
                selected = by_name[name]["id"]
                requests.post(api + "/api/project", json={"project_id": selected}, timeout=10).raise_for_status()
                response = requests.post(api + "/api/chat", json={"message": prompt, "provider": "manifest",
                    "project_id": selected, "session_id": uuid.uuid4().hex}, timeout=(10, 300), stream=True)
                response.raise_for_status()
                events = [json.loads(line.decode("utf-8")) for line in response.iter_lines() if line]
                done = next((e for e in events if e.get("type") == "done"), {})
                steps = [e.get("step", {}) for e in events if e.get("type") == "step"]
                sources = {s for step in steps for s in step.get("sources", [])}
                case = {"project": name, "prompt": prompt, "events": events,
                    "rag_succeeded": any(s.get("tool") == "RagTool" and s.get("success") for s in steps),
                    "expected_sources_returned": all(s in sources for s in wanted),
                    "answer": done.get("response", "")}
                report["model_cases"].append(case)
                assert case["rag_succeeded"] and case["expected_sources_returned"] and case["answer"], name
        checks["source_project_unchanged"] = snapshot(project) == project_before
        checks["candidate_files_unchanged"] = snapshot(candidates) == candidate_before
        assert checks["source_project_unchanged"] and checks["candidate_files_unchanged"]
        report["result"] = "completed"
    except Exception as exc:
        report["result"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if service:
            service.close()
        if child:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        log.close()
        path = base / "report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"REPORT={path} RESULT={report.get('result')}", flush=True)


if __name__ == "__main__":
    main()
