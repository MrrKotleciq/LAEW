from pathlib import Path
from unittest.mock import MagicMock, patch

from laew.web import WorkspaceService, make_handler


def test_status_reports_provider_and_model_without_fabricating_values(tmp_path):
    service = WorkspaceService(tmp_path / "manifest.yaml")
    service._ensure_runtime = MagicMock(side_effect=lambda *_: setattr(service, "_provider_name", "ollama"))
    service._model = "qwen"
    result = service.status()
    assert result["available"] is True
    assert result["provider"] == "ollama"
    assert result["model"] == "qwen"


def test_chat_returns_executor_result_and_real_step_summary(tmp_path):
    service = WorkspaceService(tmp_path / "manifest.yaml")
    step = MagicMock(step_number=1, tool_name="filesystem", operation="view_file")
    step.tool_result = MagicMock(success=True, error_message=None)
    result = MagicMock(success=True, final_response="Done", steps=[step], prompt_tokens=3, completion_tokens=2, total_tokens=5)
    service._ensure_runtime = MagicMock()
    service._executor = MagicMock(); service._executor.run.return_value = result
    status, body = service.chat("inspect")
    assert status == 200 and body["response"] == "Done"
    assert body["steps"] == [{"number": 1, "tool": "filesystem", "operation": "view_file", "success": True, "error": None}]


def test_chat_rejects_empty_messages(tmp_path):
    status, body = WorkspaceService(tmp_path / "manifest.yaml").chat(" ")
    assert status == 422 and "required" in body["error"]


def test_handler_is_constructed_for_loopback_api(tmp_path):
    assert make_handler(WorkspaceService(Path(tmp_path / "manifest.yaml"))).__name__ == "Handler"


def test_explicit_llamacpp_uses_registry_path_and_discovery(tmp_path):
    service = WorkspaceService(tmp_path / "manifest.yaml")
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


def test_provider_error_does_not_fall_back_to_manifest(tmp_path):
    service = WorkspaceService(tmp_path / "manifest.yaml")
    with patch("laew.web.load_manifest", return_value={}), patch("laew.web.build_explicit_provider", side_effect=RuntimeError("llama.cpp unavailable")), patch("laew.web.build_provider_for_role") as fallback:
        status = service.status("llama.cpp")
    assert status["available"] is False
    assert "unavailable" in status["error"]
    fallback.assert_not_called()


def test_browser_client_posts_message_and_provider_to_chat_route():
    """Keep the static client and backend request contract aligned."""
    client = Path("laew/ui/app.js").read_text(encoding="utf-8")
    assert "fetch('/api/chat'" in client
    assert "method:'POST'" in client
    assert "JSON.stringify({message,provider:provider.value})" in client
    assert "finally{send.disabled=false;provider.disabled=false" in client
