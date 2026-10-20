"""Loopback-only HTTP boundary for the LAEW browser workbench.

The module intentionally uses the Python standard library: the first web
slice needs no second runtime, external service, or permissive CORS policy.
"""

from __future__ import annotations

import json
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


class WorkspaceService:
    """Owns one Chief Agent conversation for one local browser session."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self._lock = threading.Lock()
        self._agent: Optional[Agent] = None
        self._executor: Optional[AgentExecutor] = None
        self._provider_name: Optional[str] = None
        self._model: Optional[str] = None
        self._error: Optional[str] = None
        self._selection = "manifest"

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
        agent = Agent(
            config=AgentConfig(
                name="laew-web-chief", model=model,
                context_budget=context_budget_from_manifest(manifest),
            ),
            provider=provider,
            tools=build_shared_tools(terminal_allowlist_from_manifest(manifest)),
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
                self._ensure_runtime(selection)
            return {"available": True, "provider": self._provider_name, "model": self._model,
                    "selection": self._selection, "project": str(self.manifest_path.parent.parent.resolve()), "error": None}
        except (OSError, ManifestError, LLMError, RuntimeError, ValueError) as exc:
            self._error = str(exc)
            return {"available": False, "provider": self._provider_name, "model": self._model,
                    "selection": selection, "project": None, "error": self._error}

    def chat(self, message: str, selection: object = "manifest") -> tuple[int, dict[str, Any]]:
        if not isinstance(message, str) or not message.strip():
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "A non-empty message is required."}
        try:
            with self._lock:
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
            if parsed.path == "/api/status":
                selection = parse_qs(parsed.query).get("provider", ["manifest"])[0]
                self._json(HTTPStatus.OK, service.status(selection)); return
            requested = "index.html" if self.path in ("/", "/index.html") else self.path.lstrip("/")
            if requested not in {"index.html", "app.js", "app.css"}:
                self.send_error(HTTPStatus.NOT_FOUND); return
            data = (static_root / requested).read_bytes()
            content_type = "text/html" if requested.endswith("html") else ("text/css" if requested.endswith("css") else "application/javascript")
            self.send_response(HTTPStatus.OK); self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/chat":
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
            status, response = service.chat(body.get("message"), body.get("provider", "manifest"))
            self._json(status, response)

    return Handler


def serve(manifest: str = "manifests/SYSTEM_MANIFEST.yaml", port: int = 8765, open_browser: bool = True) -> None:
    """Run the workbench on loopback only until interrupted."""
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(WorkspaceService(Path(manifest))))
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"LAEW UI listening on {url} (loopback only). Press Ctrl+C to stop.")
    if open_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
