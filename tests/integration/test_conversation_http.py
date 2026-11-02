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
            assert requests.post(base + "/api/conversation/rename", json={"id": chat_id, "title": "Renamed"}, timeout=3).json()["title"] == "Renamed"
            assert requests.get(base + "/api/conversations", timeout=3).json()["conversations"][0]["id"] == chat_id
            assert requests.post(base + "/api/conversation/delete", json={"id": chat_id}, timeout=3).json()["deleted"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
