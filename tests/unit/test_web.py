from pathlib import Path
import threading
import time
from unittest.mock import MagicMock, patch

from laew.web import WorkspaceService, make_handler


def make_service(tmp_path):
    project = tmp_path / "current"
    (project / ".git").mkdir(parents=True)
    return WorkspaceService(tmp_path / "manifest.yaml", project, tmp_path)


def test_status_reports_provider_and_model_without_fabricating_values(tmp_path):
    service = make_service(tmp_path)
    service._ensure_runtime = MagicMock(side_effect=lambda *_: setattr(service, "_provider_name", "ollama"))
    service._model = "qwen"
    result = service.status()
    assert result["available"] is True
    assert result["provider"] == "ollama"
    assert result["model"] == "qwen"


def test_default_project_id_matches_case_insensitive_catalog_id(tmp_path):
    project = tmp_path / "LAEW"
    project.mkdir()
    service = WorkspaceService(tmp_path / "manifest.yaml", project, tmp_path)
    listed = next(item for item in service.list_projects()["projects"] if item["name"] == "LAEW")
    assert service.list_projects()["active_project"] == listed["id"]


def test_chat_returns_executor_result_and_real_step_summary(tmp_path):
    service = make_service(tmp_path)
    step = MagicMock(step_number=1, tool_name="filesystem", operation="view_file")
    step.tool_result = MagicMock(success=True, error_message=None)
    result = MagicMock(success=True, final_response="Done", steps=[step], prompt_tokens=3, completion_tokens=2, total_tokens=5)
    service._ensure_runtime = MagicMock()
    service._executor = MagicMock(); service._executor.run.return_value = result
    status, body = service.chat("inspect")
    assert status == 200 and body["response"] == "Done"
    assert body["steps"] == [{"number": 1, "tool": "filesystem", "operation": "view_file", "success": True, "error": None, "sources": []}]


def test_chat_rejects_empty_messages(tmp_path):
    status, body = make_service(tmp_path).chat(" ")
    assert status == 422 and "required" in body["error"]


def test_handler_is_constructed_for_loopback_api(tmp_path):
    assert make_handler(make_service(tmp_path)).__name__ == "Handler"


def test_explicit_llamacpp_uses_registry_path_and_discovery(tmp_path):
    service = make_service(tmp_path)
    provider = MagicMock()
    provider.is_available.return_value = True
    with (
        patch("laew.web.load_manifest", return_value={"agent": {"llm": {"providers": []}}}),
        patch("laew.web.build_explicit_provider", return_value=provider) as build,
        patch("laew.web.resolve_llamacpp_model", return_value="server-model") as discover,
        patch("laew.web.build_shared_tools", return_value=[]),
    ):
        status = service.status("llama.cpp")
    assert status["available"] is True
    assert status["provider"] == "llama.cpp"
    assert status["model"] == "server-model"
    build.assert_called_once_with("llama.cpp")
    discover.assert_called_once_with(None, provider)


def test_manifest_default_builds_manifest_provider_and_checks_availability(tmp_path):
    service = make_service(tmp_path)
    provider = MagicMock()
    provider.is_available.return_value = True
    manifest = {"agent": {"llm": {"providers": [{"type": "ollama", "model": "qwen"}]}}}
    with (
        patch("laew.web.load_manifest", return_value=manifest),
        patch("laew.web.build_provider_for_role", return_value=provider) as build,
        patch("laew.web.resolve_model_name", return_value="qwen"),
        patch("laew.web.build_shared_tools", return_value=[]),
    ):
        status = service.status("manifest")
    assert status["available"] is True
    assert status["provider"] == "ollama"
    build.assert_called_once_with(manifest, "primary")
    provider.is_available.assert_called()


def test_explicit_unavailable_provider_is_reported_without_fallback(tmp_path):
    service = make_service(tmp_path)
    provider = MagicMock()
    provider.is_available.return_value = False
    with (
        patch("laew.web.load_manifest", return_value={"agent": {"llm": {"providers": []}}}),
        patch("laew.web.build_explicit_provider", return_value=provider),
        patch("laew.web.resolve_llamacpp_model", return_value="server-model"),
        patch("laew.web.build_provider_for_role") as fallback,
    ):
        status = service.status("llama.cpp")
    assert status["available"] is False
    assert "unavailable" in status["error"]
    fallback.assert_not_called()


def test_project_discovery_is_direct_child_git_only_and_switch_changes_tool_roots(tmp_path):
    service = make_service(tmp_path)
    second = tmp_path / "second"
    (second / ".git").mkdir(parents=True)
    (tmp_path / "not-a-project").mkdir()
    projects = service.list_projects()
    by_name = {item["name"]: item for item in projects["projects"]}
    assert set(by_name) == {"current", "second", "not-a-project"}

    old_executor = MagicMock()
    service._executor = old_executor
    status_code, result = service.select_project(by_name["second"]["id"])
    assert status_code == 200
    assert result["project"]["path"] == str(second.resolve())
    assert service._executor is None

    provider = MagicMock()
    provider.is_available.return_value = True
    manifest = {
        "agent": {"llm": {"providers": [{"type": "ollama", "model": "qwen"}]}},
        "tools": {"categories": {"terminal": {"allowlist": ["python"]}}},
    }
    with (
        patch("laew.web.load_manifest", return_value=manifest),
        patch("laew.web.build_provider_for_role", return_value=provider),
        patch("laew.web.resolve_model_name", return_value="qwen"),
    ):
        state = service.status("manifest")
    assert state["project_path"] == str(second.resolve())
    tools = list(service._agent.tools.values())
    filesystem = next(tool for tool in tools if tool.__class__.__name__ == "FilesystemTool")
    terminal = next(tool for tool in tools if tool.__class__.__name__ == "TerminalTool")
    git = next(tool for tool in tools if tool.__class__.__name__ == "GitTool")
    assert filesystem.resolver.project_root == second.resolve()
    assert terminal.workspace_root == second.resolve()
    assert terminal._allowlist == {"python"}
    assert git.repo_root == second.resolve()
    assert service._agent.history == []
    assert service.projects_root == tmp_path.resolve()
    assert service._selection == "manifest"


def test_project_selection_rejects_unlisted_outside_path(tmp_path):
    service = make_service(tmp_path)
    outside = tmp_path.parent / "outside-project"
    (outside / ".git").mkdir(parents=True)
    status, body = service.select_project(str(outside))
    assert status == 404
    assert "unavailable" in body["error"]
    status, body = service.select_project("../outside-project")
    assert status == 404


def test_empty_project_catalog_reports_no_active_project(tmp_path):
    service = WorkspaceService(tmp_path / "manifest.yaml", tmp_path / "empty", tmp_path)
    catalog = service.list_projects()
    status = service.status("llama.cpp")
    assert catalog["projects"] == []
    assert catalog["error"]
    assert status["available"] is False
    assert status["project_path"] is None


def test_provider_error_does_not_fall_back_to_manifest(tmp_path):
    service = make_service(tmp_path)
    with patch("laew.web.load_manifest", return_value={}), patch("laew.web.build_explicit_provider", side_effect=RuntimeError("llama.cpp unavailable")), patch("laew.web.build_provider_for_role") as fallback:
        status = service.status("llama.cpp")
    assert status["available"] is False
    assert "unavailable" in status["error"]
    fallback.assert_not_called()


def test_browser_client_posts_message_and_provider_to_chat_route():
    """Keep the static client and backend request contract aligned."""
    client = Path("laew/ui/app.js").read_text(encoding="utf-8")
    assert "fetch('/api/chat'" in client
    assert "method: 'POST'" in client
    assert "project_id: currentProjectId" in client
    assert "JSON.stringify({ message, provider: provider.value, project_id: currentProjectId })" in client
    assert "finally {" in client
    assert "send.disabled = false" in client
    assert "provider.disabled = false" in client
    assert "input.value = ''" in client
    assert "fetch('/api/projects'" in client
    assert "showModal()" in client
    assert "renderMarkdown" in client
    assert "readEventStream" in client
    assert "activeController?.abort()" in client


def test_chat_stream_emits_delta_before_generation_finishes(tmp_path):
    service = make_service(tmp_path)
    project_id = service.list_projects()["active_project"]
    generation_started = threading.Event()
    continue_generation = threading.Event()

    class FakeExecutor:
        def run(self, prompt, *, stream, on_delta, on_step):
            assert stream is True
            on_delta("Partial answer")
            generation_started.set()
            assert continue_generation.wait(3)
            from types import SimpleNamespace
            return SimpleNamespace(
                success=True, final_response="Partial answer complete",
                steps=[], prompt_tokens=1, completion_tokens=2, total_tokens=3,
            )

    service._ensure_runtime = lambda *_args: None
    service._executor = FakeExecutor()
    events = []
    worker = threading.Thread(
        target=service.stream_chat,
        args=("analyze", "manifest", project_id, events.append),
        daemon=True,
    )
    try:
        worker.start()
        assert generation_started.wait(2)
        assert events[0]["type"] == "start"
        assert events[1] == {"type": "delta", "text": "Partial answer"}
        assert generation_started.is_set()
        continue_generation.set()
        worker.join(2)
        assert not worker.is_alive()
        assert events[-1]["type"] == "done"
        assert events[-1]["response"] == "Partial answer complete"
    finally:
        continue_generation.set()
        if worker.ident is not None:
            worker.join(2)


def test_project_create_builds_empty_folder_and_makes_it_active(tmp_path):
    service = make_service(tmp_path)
    status, body = service.create_project("Plain Folder")
    destination = tmp_path / "Plain Folder"
    assert status == 201
    assert body["project"]["path"] == str(destination.resolve())
    assert body["active_project"] == body["project"]["id"]
    assert destination.is_dir()
    assert list(destination.iterdir()) == []
    assert service.list_projects()["active_project"] == body["active_project"]


def test_project_create_rejects_case_insensitive_duplicate(tmp_path):
    service = make_service(tmp_path)
    assert service.create_project("Sensor Hub")[0] == 201
    status, body = service.create_project("sensor hub")
    assert status == 409
    assert "already exists" in body["error"]
    assert len(service.list_projects()["projects"]) == 2


def test_project_create_rejects_invalid_windows_names(tmp_path):
    service = make_service(tmp_path)
    for name in ("", "   ", ".", "..", "../escape", "sub\\folder", "bad:name", "trailing.", "CON", "NUL.txt"):
        status, body = service.create_project(name)
        assert status == 422, name
        assert body["error"], name
    assert len(service.list_projects()["projects"]) == 1
    assert not (tmp_path.parent / "escape").exists()


def test_chat_rejects_request_queued_for_different_active_project(tmp_path):
    service = make_service(tmp_path)
    original_id = service.list_projects()["active_project"]
    other = tmp_path / "other"
    other.mkdir()
    other_id = next(item["id"] for item in service.list_projects()["projects"] if item["name"] == "other")
    assert service.select_project(other_id)[0] == 200
    service._executor = MagicMock()
    status, body = service.chat("stale prompt", "llama.cpp", expected_project_id=original_id)
    assert status == 409
    assert "changed" in body["error"]
    service._executor.run.assert_not_called()


def test_project_switch_waits_for_inflight_chat_then_resets_runtime(tmp_path):
    service = make_service(tmp_path)
    first_id = service.list_projects()["active_project"]
    other = tmp_path / "other"
    other.mkdir()
    second_id = next(item["id"] for item in service.list_projects()["projects"] if item["name"] == "other")
    started = threading.Event()
    finish = threading.Event()
    step = MagicMock(step_number=1, tool_name="", operation=None, response="Done", tool_result=None)
    run_result = MagicMock(success=True, final_response="Done", steps=[step], prompt_tokens=1, completion_tokens=1, total_tokens=2)
    service._ensure_runtime = MagicMock()
    service._executor = MagicMock()
    service._executor.run.side_effect = lambda *_args, **_kwargs: (started.set(), finish.wait(2), run_result)[2]
    chat_result = []
    chat_thread = threading.Thread(target=lambda: chat_result.append(service.chat("run", expected_project_id=first_id)))
    chat_thread.start()
    assert started.wait(1)
    switch_result = []
    switch_thread = threading.Thread(target=lambda: switch_result.append(service.select_project(second_id)))
    switch_thread.start()
    time.sleep(0.05)
    assert switch_thread.is_alive()
    finish.set()
    chat_thread.join(2); switch_thread.join(2)
    assert chat_result[0][0] == 200
    assert switch_result[0][0] == 200
    assert service._executor is None
    assert service.active_project["id"] == second_id
