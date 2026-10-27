"""Loopback-only HTTP boundary for the LAEW browser workbench.

The module intentionally uses the Python standard library: the first web
slice needs no second runtime, external service, or permissive CORS policy.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.llm.base import LLMError
from laew.manifest import ManifestError, load_manifest
from laew.runtime import (
    build_provider_for_role,
    build_explicit_provider,
    build_shared_tools,
    context_budget_from_manifest,
    resolve_model_name,
    resolve_llamacpp_model,
    terminal_allowlist_from_manifest,
)


def resolve_workspace_root(configured_root: Optional[str | Path] = None) -> Path:
    """Resolve the shared workspace root independently of the CLI launch cwd."""
    configured = configured_root or os.environ.get("LAEW_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    app_root = Path(__file__).resolve().parents[1]
    # LAEW lives in <workspace>/Projects/LAEW in the default local layout.
    if app_root.parent.name.casefold() == "projects":
        return app_root.parent.parent.resolve()
    return app_root.parent.resolve()


class WorkspaceService:
    """Owns one Chief Agent conversation for one local browser session."""

    def __init__(
        self,
        manifest_path: Path,
        project_root: Optional[Path] = None,
        projects_root: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
    ):
        self.manifest_path = manifest_path
        if workspace_root is None:
            workspace_root = projects_root.parent if projects_root is not None else resolve_workspace_root()
        self.workspace_root = Path(workspace_root).resolve()
        self.projects_root = Path(projects_root or self.workspace_root / "Projects").resolve()
        self.knowledge_root = (self.workspace_root / "Knowledge").resolve()
        app_root = Path(__file__).resolve().parents[1]
        self.default_project_root = Path(project_root).resolve() if project_root else app_root.resolve()
        self._lock = threading.Lock()
        self._agent: Optional[Agent] = None
        self._executor: Optional[AgentExecutor] = None
        self._provider_name: Optional[str] = None
        self._model: Optional[str] = None
        self._error: Optional[str] = None
        self._selection = "manifest"
        self._projects = self._discover_projects()
        try:
            default_id = self._id_for_path(self.default_project_root)
        except ValueError:
            default_id = None
        self._active_project_id = default_id if default_id in self._projects else None

    def _id_for_path(self, path: Path) -> str:
        relative = path.resolve().relative_to(self.projects_root)
        return hashlib.sha256(relative.as_posix().casefold().encode("utf-8")).hexdigest()[:16]

    def _discover_projects(self) -> dict[str, dict[str, str]]:
        """Discover all direct child directories under the trusted Projects root."""
        projects: dict[str, dict[str, str]] = {}
        self._projects_error = None
        try:
            if not self.projects_root.is_dir():
                self._projects_error = f"Projects directory is unavailable: {self.projects_root}"
                return projects
            candidates = list(self.projects_root.iterdir())
        except OSError as exc:
            self._projects_error = f"Could not read Projects directory: {exc}"
            return projects
        for candidate in candidates:
            try:
                if not candidate.is_dir():
                    continue
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(self.projects_root)
                relative = candidate.relative_to(self.projects_root).as_posix().casefold()
                project_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
            except (OSError, ValueError):
                continue
            projects[project_id] = {"id": project_id, "name": resolved.name, "path": str(resolved)}
        return dict(sorted(projects.items(), key=lambda item: item[1]["name"].casefold()))

    @property
    def active_project(self) -> dict[str, str]:
        if self._active_project_id is None:
            raise RuntimeError("No eligible project is active. Configure a projects root containing a Git project.")
        return self._projects[self._active_project_id]

    def list_projects(self) -> dict[str, Any]:
        with self._lock:
            self._projects = self._discover_projects()
            if self._active_project_id not in self._projects:
                self._active_project_id = None
            return {"projects_root": str(self.projects_root), "projects": list(self._projects.values()),
                    "active_project": self._active_project_id,
                    "error": self._projects_error or (None if self._projects else "No project folders found under the configured Projects directory.")}

    @staticmethod
    def validate_project_name(name: object) -> str:
        if not isinstance(name, str):
            raise ValueError("Enter a valid project name.")
        if not name or not name.strip():
            raise ValueError("Project name cannot be empty.")
        if len(name) > 120:
            raise ValueError("Project names must be 120 characters or fewer.")
        if name in {".", ".."} or name.endswith((" ", ".")):
            raise ValueError("Project names cannot end with a space or period.")
        if any(ord(char) < 32 or char in '<>:\"/\\|?*' for char in name):
            raise ValueError("Project name contains a character that is not valid in a Windows folder name.")
        device_name = name.split(".", 1)[0].rstrip(" .").upper()
        if device_name in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or re.fullmatch(r"(?:COM|LPT)(?:[1-9]|[¹²³])", device_name):
            raise ValueError("That name is reserved by Windows. Choose another project name.")
        return name

    def _reset_runtime(self) -> None:
        self._agent = None
        self._executor = None
        self._provider_name = None
        self._model = None
        self._error = None

    def create_project(self, name: object) -> tuple[int, dict[str, Any]]:
        try:
            safe_name = self.validate_project_name(name)
        except ValueError as exc:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
        with self._lock:
            try:
                self.projects_root.mkdir(parents=True, exist_ok=True)
                self._projects = self._discover_projects()
                if any(project["name"].casefold() == safe_name.casefold() for project in self._projects.values()):
                    return HTTPStatus.CONFLICT, {"error": "A project with that name already exists."}
                destination = self.projects_root / safe_name
                if destination.exists():
                    return HTTPStatus.CONFLICT, {"error": "A folder with that name already exists."}
                destination.mkdir()
                resolved = destination.resolve(strict=True)
                if resolved.parent != self.projects_root:
                    resolved.rmdir()
                    return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Project must be created directly under the trusted Projects directory."}
                project_id = hashlib.sha256(safe_name.casefold().encode("utf-8")).hexdigest()[:16]
                project = {"id": project_id, "name": safe_name, "path": str(resolved)}
                self._projects[project_id] = project
                self._projects = dict(sorted(self._projects.items(), key=lambda item: item[1]["name"].casefold()))
                self._active_project_id = project_id
                self._reset_runtime()
                return HTTPStatus.CREATED, {"project": project, "active_project": project_id}
            except FileExistsError:
                return HTTPStatus.CONFLICT, {"error": "A folder with that name already exists."}
            except OSError as exc:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not create project: {exc}"}

    def select_project(self, project_id: object) -> tuple[int, dict[str, Any]]:
        with self._lock:
            self._projects = self._discover_projects()
            if self._active_project_id not in self._projects:
                self._active_project_id = None
            if not isinstance(project_id, str) or project_id not in self._projects:
                return HTTPStatus.NOT_FOUND, {"error": "That project is unavailable. Refresh the project list and choose a listed project."}
            if project_id != self._active_project_id:
                self._active_project_id = project_id
                # A fresh Agent starts a new conversation so context cannot leak across projects.
                self._reset_runtime()
            return HTTPStatus.OK, {"project": self._projects[project_id], "active_project": project_id}

    @staticmethod
    def _validate_selection(selection: object) -> str:
        if selection in (None, "", "manifest"):
            return "manifest"
        if selection == "llama.cpp":
            return "llama.cpp"
        raise ValueError("Unsupported provider selection. Choose Manifest default or llama.cpp.")

    def _ensure_runtime(self, selection: object = "manifest") -> None:
        selection = self._validate_selection(selection)
        if self._executor is not None and self._selection == selection:
            return
        self._reset_runtime()
        manifest = load_manifest(self.manifest_path)
        providers = manifest.get("agent", {}).get("llm", {}).get("providers", [])
        manifest_model = providers[0].get("model") if providers else None
        if selection == "llama.cpp":
            provider = build_explicit_provider("llama.cpp")
            model = resolve_llamacpp_model(None, provider)
            provider_name = "llama.cpp"
        else:
            provider = build_provider_for_role(manifest, "primary")
            model = resolve_model_name(None, manifest_model, provider)
            provider_name = providers[0].get("type", "ollama") if providers else "ollama"
        if not provider.is_available():
            raise LLMError(
                f"{provider_name} is unavailable. Check that its local service is running.",
                code="PROVIDER_UNAVAILABLE",
            )
        agent = Agent(
            config=AgentConfig(
                name="laew-web-chief", model=model,
                context_budget=context_budget_from_manifest(manifest),
            ),
            provider=provider,
            tools=build_shared_tools(
                terminal_allowlist_from_manifest(manifest),
                project_root=Path(self.active_project["path"]),
                projects_root=self.projects_root,
                knowledge_root=self.knowledge_root,
                manifest=manifest,
            ),
        )
        self._agent = agent
        self._executor = AgentExecutor(agent)
        self._provider_name = provider_name
        self._model = model
        self._selection = selection
        self._error = None

    def status(self, selection: object = "manifest") -> dict[str, Any]:
        try:
            with self._lock:
                if self._active_project_id is None:
                    raise RuntimeError("No project is active. Select a project folder from the Projects directory.")
                self._ensure_runtime(selection)
                current = self.active_project
                return {"available": True, "provider": self._provider_name, "model": self._model,
                        "selection": self._selection, "project": current["name"],
                        "project_path": current["path"], "projects_root": str(self.projects_root),
                        "knowledge_root": str(self.knowledge_root), "error": None}
        except (OSError, ManifestError, LLMError, RuntimeError, ValueError) as exc:
            with self._lock:
                current = self._projects.get(self._active_project_id) if self._active_project_id else None
                self._error = str(exc)
                return {"available": False, "provider": self._provider_name, "model": self._model,
                        "selection": selection, "project": current["name"] if current else None,
                        "project_path": current["path"] if current else None, "projects_root": str(self.projects_root),
                        "knowledge_root": str(self.knowledge_root), "error": self._error}

    def chat(self, message: str, selection: object = "manifest", expected_project_id: Optional[str] = None) -> tuple[int, dict[str, Any]]:
        if not isinstance(message, str) or not message.strip():
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "A non-empty message is required."}
        try:
            with self._lock:
                if self._active_project_id is None:
                    raise RuntimeError("No project is active. Select a project folder from the Projects directory.")
                if expected_project_id is not None and expected_project_id != self._active_project_id:
                    return HTTPStatus.CONFLICT, {"error": "The active project changed before this message started. Review the selected project and retry."}
                self._ensure_runtime(selection)
                assert self._executor is not None
                result = self._executor.run(message.strip(), stream=False)
            steps = [
                {"number": step.step_number, "tool": step.tool_name, "operation": step.operation,
                 "success": None if step.tool_result is None else step.tool_result.success,
                 "error": None if step.tool_result is None else step.tool_result.error_message}
                for step in result.steps if step.tool_name or step.response
            ]
            if not result.success:
                return HTTPStatus.BAD_GATEWAY, {"error": result.error or "The Chief Agent did not complete the run.", "steps": steps}
            return HTTPStatus.OK, {"response": result.final_response, "provider": self._provider_name,
                                   "model": self._model, "steps": steps,
                                   "usage": {"prompt_tokens": result.prompt_tokens,
                                             "completion_tokens": result.completion_tokens,
                                             "total_tokens": result.total_tokens}}
        except (OSError, ManifestError, LLMError, RuntimeError, ValueError) as exc:
            self._error = str(exc)
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": self._error}


def make_handler(service: WorkspaceService):
    """Create a same-origin-only request handler bound to *service*."""
    static_root = Path(__file__).with_name("ui")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(data)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/projects":
                self._json(HTTPStatus.OK, service.list_projects()); return
            if parsed.path == "/api/status":
                selection = parse_qs(parsed.query).get("provider", ["manifest"])[0]
                self._json(HTTPStatus.OK, service.status(selection)); return
            requested = "index.html" if parsed.path in ("/", "/index.html") else parsed.path.lstrip("/")
            if requested not in {"index.html", "app.js", "app.css"}:
                self.send_error(HTTPStatus.NOT_FOUND); return
            data = (static_root / requested).read_bytes()
            content_type = "text/html" if requested.endswith("html") else ("text/css" if requested.endswith("css") else "application/javascript")
            self.send_response(HTTPStatus.OK); self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            if route not in {"/api/chat", "/api/project", "/api/projects"}:
                self.send_error(HTTPStatus.NOT_FOUND); return
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if origin and origin not in {f"http://{host}", f"http://127.0.0.1:{host.rsplit(':', 1)[-1]}"}:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Cross-origin requests are not allowed."}); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1_000_000: raise ValueError("Message is too large.")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON request."}); return
            if not isinstance(body, dict):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be a JSON object."}); return
            if route == "/api/projects":
                status, response = service.create_project(body.get("name"))
                self._json(status, response); return
            if route == "/api/project":
                status, response = service.select_project(body.get("project_id"))
                self._json(status, response); return
            status, response = service.chat(body.get("message"), body.get("provider", "manifest"), body.get("project_id"))
            self._json(status, response)

    return Handler


def serve(
    manifest: str = "manifests/SYSTEM_MANIFEST.yaml",
    port: int = 8765,
    open_browser: bool = True,
    projects_root: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> None:
    """Run the workbench on loopback only until interrupted."""
    root = resolve_workspace_root(workspace_root)
    application_root = Path(__file__).resolve().parents[1]
    catalog_root = Path(projects_root).expanduser().resolve() if projects_root else (root / "Projects").resolve()
    project_root = application_root if application_root.parent == catalog_root else (catalog_root / application_root.name)
    if not project_root.is_dir():
        project_root = None
    manifest_path = Path(manifest).expanduser()
    if not manifest_path.is_absolute():
        manifest_path = application_root / manifest_path
    service = WorkspaceService(manifest_path.resolve(), project_root, catalog_root, root)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(service))
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"LAEW UI listening on {url} (loopback only). Press Ctrl+C to stop.")
    if open_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
