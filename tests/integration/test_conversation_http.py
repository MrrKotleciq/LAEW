"""Persistent conversation lifecycle through the loopback boundary."""

import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import requests

from laew.console.session_store import SessionStore
from laew.llm.base import LLMResponse
from laew.web import WorkspaceService, make_handler


def test_general_conversation_http_lifecycle(tmp_path):
    class Provider:
        def is_available(self): return True
        def generate(self, messages, **kwargs): return LLMResponse(content="fixture answer", model="fixture")

    projects = tmp_path / "Projects"
    projects.mkdir()
    (tmp_path / "Knowledge").mkdir()
    service = WorkspaceService(tmp_path / "manifest", projects_root=projects, workspace_root=tmp_path)
    service._conversation_store = SessionStore(tmp_path / "sessions")
    provider = Provider()
    with (patch("laew.web.load_manifest", return_value={}),
          patch("laew.web.build_provider_for_role", return_value=provider),
          patch("laew.web.resolve_model_name", return_value="fixture"),
          patch("laew.web.build_shared_tools", return_value=[])):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            created = requests.post(base + "/api/conversations", json={"scope_type": "general", "project_id": None}, timeout=3).json()
            chat_id = created["id"]
            response = requests.post(base + "/api/chat", json={"message": "hello", "provider": "manifest",
                "project_id": None, "conversation_id": chat_id, "session_id": "session"}, timeout=5)
            assert '"type": "done"' in response.text
            history = requests.get(base + "/api/conversation", params={"id": chat_id}, timeout=3).json()
            assert [e["kind"] for e in history["events"]] == ["run", "user", "assistant", "run"]
            assert history["events"][-1]["status"] == "completed"
            assert history["events"][-1]["assistant_event_id"] == history["events"][-2]["id"]
            assert history["events"][-1]["diagnostics"]["requests"][0]["dispatched"] is True
            assert requests.post(base + "/api/conversation/rename", json={"id": chat_id, "title": "Renamed"}, timeout=3).json()["title"] == "Renamed"
            assert requests.get(base + "/api/conversations", timeout=3).json()["conversations"][0]["id"] == chat_id
            assert requests.post(base + "/api/conversation/delete", json={"id": chat_id}, timeout=3).json()["deleted"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


def test_project_conversation_diagnostics_require_matching_active_scope(tmp_path):
    projects = tmp_path / "Projects"
    for name in ("A", "B"):
        (projects / name).mkdir(parents=True)
    service = WorkspaceService(tmp_path / "manifest", projects_root=projects, workspace_root=tmp_path)
    store = service._conversation_store = SessionStore(tmp_path / "sessions")
    a, b = (service._id_for_path(projects / name) for name in ("A", "B"))
    chat = store.create_conversation("project", a)
    store.append_conversation_event(chat["id"], {
        "id": "finished", "run_id": "test", "kind": "run", "status": "completed", "content": "",
        "diagnostics": {"version": 1, "routing": {"scopes": ["project"], "prefetch": [
            {"fragments": [{"id": "private-chunk", "path": "@project/private.md"}]}
        ], "follow_up": []}, "tools": [], "requests": []},
    })
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/api/conversation"
    try:
        for active, requested in ((None, None), (None, a), (b, b), (b, a), (a, b)):
            service._active_project_id = active
            result = requests.get(url, params={"id": chat["id"], "project_id": requested}, timeout=3)
            assert result.status_code == 403 and "private.md" not in result.text
        service._active_project_id = a
        result = requests.get(url, params={"id": chat["id"], "project_id": a}, timeout=3)
        assert result.status_code == 200 and "@project/private.md" in result.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
