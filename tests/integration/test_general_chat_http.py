"""Workbench scope selection is enforced at the HTTP boundary."""

import threading
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock, patch

import requests

from laew.web import WorkspaceService, make_handler


def test_general_chat_http_rejects_stale_project_scope(tmp_path):
    projects = tmp_path / "Projects"
    project = projects / "Example"
    project.mkdir(parents=True)
    (tmp_path / "Knowledge").mkdir()
    service = WorkspaceService(tmp_path / "manifest", project, projects, tmp_path)
    project_id = service.list_projects()["active_project"]
    provider = MagicMock()
    provider.is_available.return_value = True
    with (patch("laew.web.load_manifest", return_value={}),
          patch("laew.web.build_provider_for_role", return_value=provider),
          patch("laew.web.resolve_model_name", return_value="test")):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            response = requests.post(base + "/api/project", json={"project_id": None}, timeout=3)
            assert response.status_code == 200 and response.json()["active_project"] is None
            status = requests.get(base + "/api/status", timeout=3).json()
            assert status["available"] and status["project"] is None
            response = requests.post(base + "/api/chat", json={"message": "hello", "project_id": project_id}, timeout=3)
            assert response.json()["type"] == "error"
            assert "changed" in response.json()["error"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
