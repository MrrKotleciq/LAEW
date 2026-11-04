"""Loopback-only HTTP boundary for the LAEW browser workbench.

The module intentionally uses the Python standard library: the first web
slice needs no second runtime, external service, or permissive CORS policy.
"""

from __future__ import annotations

import json
import logging
import hashlib
import os
import re
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.agent.executor import StreamCancelled
from laew.llm.base import LLMError
from laew.llm.cancellation import Cancellation
from laew.cloud_chat import CLOUD_PROVIDERS, CloudChatService, CloudError
from laew.manifest import ManifestError, load_manifest
from laew.project_config import load_project_settings, save_project_language, save_project_settings
from laew.security.permissions import PermissionBroker
from laew.runtime import (
    build_provider_for_role,
    build_explicit_provider,
    build_shared_tools,
    build_rag_tool,
    context_budget_from_manifest,
    resolve_model_name,
    resolve_llamacpp_model,
    terminal_allowlist_from_manifest,
)

_UNSPECIFIED_SCOPE = object()


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
        registered_projects: Optional[list[Path]] = None,
    ):
        self.manifest_path = manifest_path
        if workspace_root is None:
            workspace_root = projects_root.parent if projects_root is not None else resolve_workspace_root()
        self.workspace_root = Path(workspace_root).resolve()
        self.projects_root = Path(projects_root or self.workspace_root / "Projects").resolve()
        self.knowledge_root = (self.workspace_root / "Knowledge").resolve()
        self.registered_projects = tuple(Path(path).expanduser().resolve() for path in (registered_projects or ()))
        app_root = Path(__file__).resolve().parents[1]
        self.default_project_root = Path(project_root).resolve() if project_root else app_root.resolve()
        self._lock = threading.Lock()
        self._runs_lock = threading.Lock()
        self._runs = {}
        self._early_cancellations = {}
        self._sync_lock = threading.Lock()
        self._sync_bases = {}
        self._scheduler = None
        self._cloud = None
        self._agent: Optional[Agent] = None
        self._permissions = None
        self._executor: Optional[AgentExecutor] = None
        self._provider_name: Optional[str] = None
        self._model: Optional[str] = None
        self._error: Optional[str] = None
        self._selection = "manifest"
        self._account_id = None
        self._session_id = None
        self._conversations = {}
        self._conversation_store = None
        self._memory_lock = threading.RLock()
        self._memory = None
        self._memory_worker = None
        self._knowledge = None
        self._knowledge_worker = None
        self._knowledge_lock = threading.RLock()
        self._projects = self._discover_projects()
        try:
            default_id = self._id_for_path(self.default_project_root)
        except ValueError:
            default_id = None
        self._active_project_id = default_id if default_id in self._projects else None

    def _id_for_path(self, path: Path) -> str:
        from laew.rag.identity import canonical_project_path
        return hashlib.sha256(canonical_project_path(path).encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _run_key(session_id, run_id):
        pattern = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
        if not isinstance(session_id, str) or not isinstance(run_id, str):
            return None
        if not re.fullmatch(pattern, session_id) or not re.fullmatch(pattern, run_id):
            return None
        return session_id, run_id

    def register_run(self, session_id, run_id):
        key = self._run_key(session_id, run_id)
        if key is None:
            return None
        token = Cancellation()
        with self._runs_lock:
            if key in self._runs:
                raise ValueError("Run ID is already active.")
            self._runs[key] = token
            cancelled = self._early_cancellations.pop(key, 0) > time.monotonic()
        if cancelled:
            token.cancel()
        return token

    def cancel_run(self, session_id, run_id):
        key = self._run_key(session_id, run_id)
        if key is None:
            return False
        with self._runs_lock:
            token = self._runs.get(key)
            if token is None:
                now = time.monotonic()
                self._early_cancellations = {k: expiry for k, expiry in self._early_cancellations.items() if expiry > now}
                if len(self._early_cancellations) >= 512:
                    return False
                self._early_cancellations[key] = now + 60
        if token is not None:
            token.cancel()
        return True

    def unregister_run(self, session_id, run_id, token):
        key = self._run_key(session_id, run_id)
        with self._runs_lock:
            if self._runs.get(key) is token:
                self._runs.pop(key, None)

    def _discover_projects(self) -> dict[str, dict[str, str]]:
        """Discover all direct child directories under the trusted Projects root."""
        projects: dict[str, dict[str, str]] = {}
        self._projects_error = None
        try:
            if not self.projects_root.is_dir():
                self._projects_error = f"Projects directory is unavailable: {self.projects_root}"
                candidates = []
            else:
                candidates = list(self.projects_root.iterdir())
        except OSError as exc:
            self._projects_error = f"Could not read Projects directory: {exc}"
            candidates = []
        for candidate in candidates:
            try:
                if not candidate.is_dir():
                    continue
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(self.projects_root)
                project_id = self._id_for_path(resolved)
            except (OSError, ValueError):
                continue
            projects[project_id] = {"id": project_id, "name": resolved.name, "path": str(resolved)}
        for candidate in self.registered_projects:
            if candidate.is_dir():
                project_id = self._id_for_path(candidate)
                projects[project_id] = {"id": project_id, "name": candidate.name, "path": str(candidate)}
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
                if self._active_project_id is not None:
                    self._reset_runtime()
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
        self._permissions = None
        self._executor = None
        self._provider_name = None
        self._model = None
        self._error = None

    def conversation_store(self):
        if self._conversation_store is None:
            from laew.console.session_store import conversation_store_from_manifest
            self._conversation_store = conversation_store_from_manifest(load_manifest(self.manifest_path), self.manifest_path)
        return self._conversation_store

    def memory(self):
        with self._memory_lock: return self._get_memory()

    def _get_memory(self):
        if self._memory is None:
            from laew.memory.integration import build_memory, MemoryWorker, extraction_provider
            manifest=load_manifest(self.manifest_path)
            self._memory=build_memory(manifest,self.manifest_path)
            self._memory_worker=MemoryWorker(self._memory,self.conversation_store(),
                lambda selection: extraction_provider(manifest,selection,self.cloud))
        return self._memory

    def memory_selection(self):
        return {"provider":self._selection,"model":self._model,"account_id":self._account_id}

    def knowledge(self):
        with self._knowledge_lock:
            if self._knowledge is None:
                from laew.knowledge.integration import build_knowledge, KnowledgeWorker
                from laew.memory.integration import extraction_provider
                from laew.rag.sync import synchronize_scope
                manifest = load_manifest(self.manifest_path)
                def broker(project_id):
                    project = self._discover_projects().get(project_id) if project_id else None
                    if project_id and project is None:
                        raise ValueError('Proposal project is unavailable.')
                    root = project['path'] if project else None
                    mode = load_project_settings(root).get('permission_mode', 'auto') if root else 'auto'
                    return PermissionBroker(root, mode)
                def sync(path):
                    kb = self._sync_base()
                    if not (kb._vector_store_config or {}).get('enabled'):
                        raise RuntimeError('Persistent Global RAG is disabled.')
                    return synchronize_scope(kb, 'global')
                self._knowledge = build_knowledge(manifest,
                    self.conversation_store(), projects_root=self.projects_root,
                    knowledge_root=self.knowledge_root, broker_factory=broker, sync_callback=sync,
                    discovery_base=lambda: next(iter(self._sync_bases.copy().values()), None))
                self._knowledge_worker = KnowledgeWorker(self._knowledge, self.conversation_store(),
                    lambda selection: extraction_provider(manifest, selection, self.cloud))
            return self._knowledge

    def knowledge_selection(self, project_id=None):
        if self.knowledge().settings()['model_source'] == 'active':
            return self.memory_selection() if project_id == self._active_project_id and self._model else None
        return self.memory().store.settings(project_id)['extraction_model']

    def knowledge_request(self, action, body):
        import sqlite3
        from laew.console.session_store import SessionStoreError
        try:
            project_id = body.get('project_id') or None
            if project_id is not None and project_id not in self._discover_projects():
                raise ValueError('Project is unavailable.')
            service = self.knowledge()
            if action == 'state':
                return 200, {'settings': service.settings(),
                    'proposals': service.list_proposals(project_id), 'status': service.status(project_id),
                    'extraction_model': self.knowledge_selection(project_id)}
            if action == 'settings':
                return 200, service.save_settings(body.get('settings'))
            if action == 'preview':
                return 200, service.preview(body.get('id'), project_id)
            if action == 'edit':
                return 200, service.edit(body.get('id'), project_id, body.get('version'), body.get('content'),
                    target=body.get('target'), kind=body.get('kind'))
            if action == 'decide':
                result = service.decide(body.get('id'), project_id, body.get('version'), body.get('action'))
                self._knowledge_worker.request()
                return 200, result
            if action == 'analyze':
                conversation = self.conversation_store().load_conversation(body.get('conversation_id'))
                if conversation['project_id'] != project_id:
                    raise ValueError('Conversation scope does not match selection.')
                selection = self.knowledge_selection(project_id)
                if selection is None:
                    raise ValueError('Choose an extraction model or start a chat with the active model option enabled.')
                key = service.enqueue(conversation, selection, manual=True)
                self._knowledge_worker.request()
                return 200, {'queued': key, 'message': 'Analysis queued.' if key else 'No new completed turns or analysis already queued.'}
            if action == 'sync':
                self._knowledge_worker.request()
                return 200, {'message': 'Pending knowledge indexing queued.'}
            raise ValueError('Unknown knowledge operation.')
        except (ValueError, TypeError, KeyError, FileNotFoundError, SessionStoreError) as exc:
            return 400, {'error': str(exc)}
        except (OSError, sqlite3.Error):
            return 503, {'error': 'Knowledge storage is unavailable.'}

    def defaults(self):
        from laew.settings import settings_path, read_defaults
        return read_defaults(settings_path(load_manifest(self.manifest_path) if Path(self.manifest_path).exists() else {},self.manifest_path))

    def memory_request(self, action, body):
        import sqlite3
        from laew.memory.categories import CATEGORY_DESCRIPTIONS, InvalidMemoryCategory
        try:
            memory=self.memory(); store=memory.store
            project_id=body.get('project_id')
            if project_id is not None and project_id not in self._discover_projects():
                raise ValueError('Project is unavailable.')
            def authorized(record):
                if record['scope']=='project' and record['project_id']!=project_id:
                    raise ValueError('Memory is outside the selected project scope.')
                return record
            if action=='state':
                return 200, {'settings':store.settings(),'categories':dict(CATEGORY_DESCRIPTIONS),'memories':store.list_memories(project_id),
                    'proposals':memory.proposals(project_id),'status':memory.status()}
            if action=='get': return 200,authorized(store.get(body.get('id')))
            if action=='settings':
                result=store.save_settings(body.get('settings')); self._memory_worker.request(); return 200,result
            if action=='add': return 200,store.remember(body.get('content'),body.get('scope'),project_id if body.get('scope')=='project' else None,body.get('category'))
            if action in ('update','delete'):
                authorized(store.get(body.get('id')))
                if action=='update': return 200,store.update(body.get('id'),body.get('content'),body.get('version'),body.get('category'))
                store.delete(body.get('id'),body.get('version')); return 200,{'deleted':True}
            if action=='decide':
                with store.connection() as db:
                    row=db.execute('SELECT * FROM memory_proposals WHERE id=?',(body.get('id'),)).fetchone()
                if not row: raise ValueError('Proposal not found.')
                authorized(row)
                if type(body.get('approve')) is not bool: raise ValueError('Choose approve or reject.')
                result=memory.decide(body['id'],body['approve'],body.get('content')); self._memory_worker.request(); return 200,result
            if action=='analyze':
                conversation=self.conversation_store().load_conversation(body.get('conversation_id'))
                if conversation['project_id']!=project_id: raise ValueError('Conversation scope does not match selection.')
                selection=body.get('selection') or self.memory_selection()
                key=memory.enqueue(conversation,selection,manual=True)
                self._memory_worker.request()
                return 200,{'queued':key,'message':'Analysis queued.' if key else 'No new completed turns, or analysis already pending.'}
            if action in ('sync','rebuild'):
                self._memory_worker.request(rebuild=action=='rebuild')
                return 200,{'message':'Memory synchronization queued.'}
            raise ValueError('Unknown memory operation.')
        except InvalidMemoryCategory as exc:
            return 400,{'error':str(exc),'error_code':'ERR_INVALID_INPUT',**exc.details()}
        except (ValueError,TypeError,KeyError,FileNotFoundError) as exc: return 400,{'error':str(exc)}
        except (OSError,sqlite3.Error): return 503,{'error':'SQLite memory storage is unavailable.'}

    def application_settings(self, body=None):
        if not self._lock.acquire(blocking=False): return 409, {'error':'Wait for the active run to finish.'}
        try: return self._application_settings(body)
        finally: self._lock.release()

    def _application_settings(self, body=None):
        import sqlite3
        from laew.settings import settings_path,read_defaults,save_defaults
        from laew.project_config import project_overrides
        try:
            path=settings_path(load_manifest(self.manifest_path),self.manifest_path)
            if body is None: return 200,{'defaults':read_defaults(path)}
            if 'defaults' in body:
                result=save_defaults(path,body['defaults'])
                self._conversations.clear(); self._session_id=None; self._reset_runtime()
                return 200,{'defaults':result}
            project=self._discover_projects().get(body.get('project_id'))
            if not project: raise ValueError('Project is unavailable.')
            if 'memory_overrides' in body:
                self.memory().store.save_project_settings(project['id'],body['memory_overrides'])
            if 'overrides' in body:
                updates=body['overrides']
                if not isinstance(updates,dict) or set(updates)-{'documentation_language'}: raise ValueError('Unknown project setting.')
                save_project_settings(project['path'],updates)
                if project['id']==self._active_project_id: self._conversations.clear(); self._session_id=None; self._reset_runtime()
            overrides=project_overrides(project['path'])
            return 200,{'project_id':project['id'],'name':project['name'],'defaults':read_defaults(path),'overrides':overrides,
                'effective':load_project_settings(project['path'],read_defaults(path)), 'memory_defaults':self.memory().store.settings(), 'memory_overrides':self.memory().store.project_settings(project['id']), 'memory_effective':self.memory().store.settings(project['id'])}
        except (OSError,ValueError,TypeError,KeyError) as exc: return 400,{'error':str(exc)}
        except sqlite3.Error: return 503,{'error':'SQLite memory settings are unavailable.'}

    def create_conversation(self, scope, project_id):
        from laew.console.session_store import SessionStoreError
        if scope == "project" and project_id not in self._discover_projects():
            raise SessionStoreError("Project is unavailable.")
        return self.conversation_store().create_conversation(scope, project_id)

    def read_conversation(self, conversation_id, project_id):
        from laew.console.session_store import SessionStoreError, _valid_turn_diagnostics
        store = self.conversation_store()
        conversation = store.load_conversation(conversation_id)
        if (project_id != self._active_project_id or project_id != conversation["project_id"]
                or (project_id is not None and project_id not in self._discover_projects())):
            raise PermissionError("Conversation scope does not match the active scope.")
        if any(event["kind"] == "run" and event["status"] == "running"
               for event in {e.get("run_id"): e for e in conversation["events"] if e["kind"] == "run"}.values()):
            try:
                with store.conversation_run(conversation_id):
                    store.recover_interrupted_runs(conversation_id)
                    conversation = store.load_conversation(conversation_id)
            except SessionStoreError as exc:
                if str(exc) != "conversation is busy":
                    raise
        for event in conversation["events"]:
            if "diagnostics" in event and not _valid_turn_diagnostics(event["diagnostics"]):
                event.pop("diagnostics")
        return conversation

    def _sync_base(self, project_root=None):
        root = Path(project_root).resolve() if project_root is not None else None
        with self._sync_lock:
            if root not in self._sync_bases:
                manifest = load_manifest(self.manifest_path)
                tool = build_rag_tool(manifest, project_root=root, projects_root=self.projects_root,
                                      knowledge_root=self.knowledge_root, general=root is None)
                self._sync_bases[root] = tool._pipeline.knowledge_base
            return self._sync_bases[root]

    def start_sync(self):
        try:
            self.knowledge(); self._knowledge_worker.start()
        except Exception: logging.getLogger(__name__).exception('Knowledge worker unavailable')
        try:
            self.memory(); self._memory_worker.start()
        except Exception: logging.getLogger(__name__).exception('Memory worker unavailable')
        from laew.rag.sync import SyncScheduler
        if self._scheduler is None:
            self._scheduler = SyncScheduler(self._sync_base)
            project = self._projects.get(self._active_project_id)
            self._scheduler.start(project["path"] if project else None)

    def close(self):
        if self._knowledge_worker is not None:
            self._knowledge_worker.close()
        if self._memory_worker is not None:
            self._memory_worker.close()
        if self._cloud is not None:
            self._cloud.close()
        if self._scheduler is not None:
            self._scheduler.close()

    @property
    def cloud(self):
        with self._runs_lock:
            if self._cloud is None: self._cloud = CloudChatService()
            return self._cloud

    def cloud_request(self, route, body):
        try:
            for field in ("provider", "model", "account_id", "project_id", "attempt_id"):
                if body.get(field) is not None and not isinstance(body[field], str):
                    raise CloudError("INVALID_REQUEST", "Invalid cloud request field.")
            session = body.get("session_id")
            if not isinstance(session, str) or not 16 <= len(session) <= 128:
                raise CloudError("INVALID_REQUEST", "A browser session is required.")
            if route == "/api/cloud/status":
                return HTTPStatus.OK, self.cloud.status(session)
            if route == "/api/cloud/key":
                from laew.api_credentials import save_api_key
                if not self._lock.acquire(blocking=False):
                    raise CloudError("BUSY", "Wait for the active run before changing credentials.")
                try:
                    save_api_key(body.get("provider"), body.get("api_key"))
                    return HTTPStatus.OK, {"configured": True, "message": "Saved to the Windows user environment and applied to this backend."}
                finally:
                    self._lock.release()
            if route == "/api/cloud/models":
                if body.get("provider") not in CLOUD_PROVIDERS:
                    manifest = load_manifest(self.manifest_path)
                    provider = (build_explicit_provider("llama.cpp") if body.get("provider") == "llama.cpp"
                                else build_provider_for_role(manifest, "primary"))
                    return HTTPStatus.OK, {"models": [{"id": m, "label": m} for m in provider.list_models()]}
                credential, _ = self.cloud.credential(body.get("provider"), body.get("account_id"))
                return HTTPStatus.OK, {"models": self.cloud.transport.models(credential, body.get("provider"))}
            if route in {"/api/cloud/history", "/api/cloud/new"}:
                if not self._lock.acquire(blocking=False):
                    raise CloudError("BUSY", "Wait for the active run before changing conversation history.")
                try:
                    agent = self._conversations.get((session, body.get("project_id")), {}).get("agent")
                    if route.endswith("/new") and agent:
                        agent.reset_history()
                    history = [{"role": m.role.value, "content": m.content} for m in (agent.history if agent else [])
                               if m.role.value in {"user", "assistant"} and not m.tool_calls]
                    return HTTPStatus.OK, {"messages": history}
                finally:
                    self._lock.release()
            if route == "/api/cloud/auth/start":
                return HTTPStatus.OK, self.cloud.auth.start(session, body.get("account_id") or None)
            if route == "/api/cloud/auth/cancel":
                return HTTPStatus.OK, self.cloud.auth.cancel_attempt(session, body.get("attempt_id"))
            if route == "/api/cloud/auth/logout":
                return HTTPStatus.OK, self.cloud.logout(body.get("account_id"))
            return HTTPStatus.NOT_FOUND, {"error": "Unknown cloud operation."}
        except (CloudError, LLMError, ManifestError) as exc:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc), "code": getattr(exc, "code", "CONFIGURATION")}

    def sync_status(self):
        from laew.rag.sync import sync_status
        try:
            project = self._projects.get(self._active_project_id)
            kb = self._sync_base(project["path"] if project else None)
            return {"project": sync_status(kb, "project") if project else None, "global": sync_status(kb, "global")}
        except Exception:
            return {"error": "Synchronization status unavailable. Check ChromaDB and configuration, then retry."}

    def request_sync(self, scope):
        if scope not in ("project", "global"):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Choose project or global synchronization."}
        project = self._projects.get(self._active_project_id)
        if scope == "project" and project is None:
            return HTTPStatus.CONFLICT, {"error": "Select a project first."}
        if self._scheduler is None:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Synchronization service is unavailable."}
        self._scheduler.request(scope, project["path"] if project else None)
        return HTTPStatus.ACCEPTED, {"message": f"{scope} synchronization requested."}

    def _call_tool(self, tool, operation, args, emit, session_id=None, cancellation=None):
        options = {"cancellation": cancellation} if cancellation is not None else {}
        result = self._permissions.call(tool, operation, args, emit, session_id, **options)
        if result.success and tool.name == "FilesystemTool" and operation == "view_file" and isinstance(result.data, dict):
            path = tool.resolver.resolve(args["file_path"])
            alias = tool.resolver.get_alias_for_path(path)
            if alias in {"@knowledge", "@project"}:
                root = tool.resolver.knowledge_root if alias == "@knowledge" else tool.resolver.project_root
                result.data["sources"] = [f"{alias}/{path.relative_to(root).as_posix()}"]
        if result.success and operation == "write_knowledge_note":
            status, detail = self.request_sync("global")
            result.data["synchronization"] = "requested" if status == HTTPStatus.ACCEPTED else "not requested"
            result.data["synchronization_detail"] = detail
        return result

    def project_settings(self):
        with self._lock:
            try:
                project = self.active_project
                settings = load_project_settings(project["path"], self.defaults())
                mode = settings.get("permission_mode", "auto")
                if mode not in {"auto", "manual", "restricted"}:
                    raise ValueError("Invalid permission mode")
                return HTTPStatus.OK, {"project_id": project["id"], **settings, "permission_mode": mode}
            except (OSError, ValueError, RuntimeError):
                return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Project settings are unavailable or invalid. Check the project settings file."}

    def update_project_settings(self, project_id, language):
        with self._lock:
            try:
                project = self.active_project
                if project_id != project["id"]:
                    return HTTPStatus.CONFLICT, {"error": "The active project changed. Refresh settings and retry."}
                settings = save_project_language(project["path"], language)
                if self._agent is not None:
                    self._agent.config.documentation_language = settings["documentation_language"]
                if self._executor is not None:
                    self._executor._system_prompt_cache = None
                return HTTPStatus.OK, {"project_id": project["id"], **settings}
            except ValueError as exc:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
            except (OSError, RuntimeError):
                return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Could not save project settings. Check project directory permissions."}

    def update_permission_mode(self, project_id, mode):
        with self._lock:
            try:
                project = self.active_project
                if project_id != project["id"]:
                    return HTTPStatus.CONFLICT, {"error": "The active project changed."}
                if mode not in ("auto", "manual", "restricted"):
                    return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Invalid permission mode."}
                save_project_settings(project["path"], {"permission_mode": mode})
                if self._permissions is not None:
                    self._permissions.mode = mode
                return HTTPStatus.OK, {"project_id": project_id, "permission_mode": mode}
            except (OSError, ValueError, RuntimeError):
                return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Could not save project permissions."}

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
                project_id = self._id_for_path(resolved)
                project = {"id": project_id, "name": safe_name, "path": str(resolved)}
                self._projects[project_id] = project
                self._projects = dict(sorted(self._projects.items(), key=lambda item: item[1]["name"].casefold()))
                self._active_project_id = project_id
                self._reset_runtime()
                if self._scheduler is not None:
                    self._scheduler.request("project", project["path"])
                return HTTPStatus.CREATED, {"project": project, "active_project": project_id}
            except FileExistsError:
                return HTTPStatus.CONFLICT, {"error": "A folder with that name already exists."}
            except OSError as exc:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not create project: {exc}"}

    def select_project(self, project_id: object) -> tuple[int, dict[str, Any]]:
        with self._lock:
            self._projects = self._discover_projects()
            if self._active_project_id not in self._projects:
                if self._active_project_id is not None:
                    self._reset_runtime()
                self._active_project_id = None
            if project_id is None:
                if self._active_project_id is not None:
                    self._active_project_id = None
                    self._reset_runtime()
                return HTTPStatus.OK, {"project": None, "active_project": None}
            if not isinstance(project_id, str) or project_id not in self._projects:
                return HTTPStatus.NOT_FOUND, {"error": "That project is unavailable. Refresh the project list and choose a listed project."}
            if project_id != self._active_project_id:
                self._active_project_id = project_id
                # A fresh Agent starts a new conversation so context cannot leak across projects.
                self._reset_runtime()
            if self._scheduler is not None:
                self._scheduler.request("project", self._projects[project_id]["path"])
            return HTTPStatus.OK, {"project": self._projects[project_id], "active_project": project_id}

    @staticmethod
    def _validate_selection(selection: object) -> str:
        if selection in (None, "", "manifest"):
            return "manifest"
        if isinstance(selection, str) and selection in {"llama.cpp", *CLOUD_PROVIDERS}:
            return selection
        raise ValueError("Unsupported provider selection.")

    def _activate_session(self, session_id, conversation_id=None):
        key = (session_id, self._active_project_id, conversation_id) if conversation_id else (session_id, self._active_project_id)
        saved = self._conversations.get(key)
        if self._session_id == key:
            return
        if self._session_id is None and self._executor is not None:
            self._session_id = key
            return
        self._reset_runtime()
        self._session_id = key
        if saved:
            self._agent, self._executor, self._permissions = saved["agent"], saved["executor"], saved["permissions"]
            self._selection, self._model = saved["selection"], saved["model"]
            self._provider_name, self._account_id = saved["provider"], saved["account_id"]

    def _ensure_runtime(self, selection: object = "manifest", model=None, account_id=None) -> None:
        selection = self._validate_selection(selection)
        if (self._executor is not None and self._selection == selection
                and (model is None or self._model == model) and self._account_id == account_id):
            return
        manifest = load_manifest(self.manifest_path)
        providers = manifest.get("agent", {}).get("llm", {}).get("providers", [])
        manifest_model = providers[0].get("model") if providers else None
        if selection in CLOUD_PROVIDERS:
            if not isinstance(model, str) or not model.strip() or len(model) > 200:
                raise CloudError("MODEL_REQUIRED", "Choose an exact cloud model ID first.")
            model = model.strip()
            provider = self.cloud.provider(selection, account_id)
            provider_name = selection
        elif selection == "llama.cpp":
            provider = build_explicit_provider("llama.cpp")
            model = resolve_llamacpp_model(model, provider)
            provider_name = "llama.cpp"
        else:
            provider = build_provider_for_role(manifest, "primary")
            model = resolve_model_name(model, manifest_model, provider)
            provider_name = providers[0].get("type", "ollama") if providers else "ollama"
        if not provider.is_available():
            raise LLMError(
                f"{provider_name} is unavailable. Check that its local service is running.",
                code="PROVIDER_UNAVAILABLE",
            )
        if self._agent is not None:
            self._agent.providers = [provider]
            self._agent._current_provider_index = 0
            self._agent.config.model = model
            self._executor._system_prompt_cache = None
        else:
            project = self._projects.get(self._active_project_id)
            general = project is None
            if general:
                for registered in self.registered_projects:
                    if (registered.is_relative_to(self.knowledge_root)
                            or self.knowledge_root.is_relative_to(registered)):
                        raise ValueError("Global Knowledge overlaps a registered project.")
            settings = load_project_settings(project["path"], self.defaults()) if project else {}
            agent = Agent(
                config=AgentConfig(
                    name="laew-web-chief", model=model,
                    documentation_language=settings.get("documentation_language", "en"),
                    project_scope=not general,
                    context_budget=context_budget_from_manifest(manifest),
                ),
                provider=provider,
                tools=build_shared_tools(
                    terminal_allowlist_from_manifest(manifest),
                    project_root=Path(project["path"]) if project else None,
                    projects_root=self.projects_root,
                    knowledge_root=self.knowledge_root,
                    manifest=manifest,
                    general=general,
                ),
            )
            self._agent = agent
            mode = settings.get("permission_mode", "auto")
            if mode not in {"auto", "manual", "restricted"}:
                raise ValueError("Invalid project permission mode.")
            self._permissions = PermissionBroker(Path(project["path"]) if project else None, mode)
            self._executor = AgentExecutor(agent)
        self._provider_name = provider_name
        self._model = model
        self._selection = selection
        self._account_id = account_id
        self._error = None
        self._conversations[self._session_id or (None, self._active_project_id)] = {
            "agent": self._agent, "executor": self._executor, "permissions": self._permissions,
            "selection": selection, "model": model, "provider": provider_name, "account_id": account_id}

    def status(self, selection: object = "manifest", model=None, session_id=None) -> dict[str, Any]:
        try:
            with self._lock:
                if session_id is not None:
                    self._activate_session(session_id)
                if model:
                    self._ensure_runtime(selection, model)
                else:
                    self._ensure_runtime(selection)
                current = self._projects.get(self._active_project_id)
                return {"available": True, "provider": self._provider_name, "model": self._model,
                        "selection": self._selection, "project": current["name"] if current else None,
                        "project_path": current["path"] if current else None, "projects_root": str(self.projects_root),
                        "knowledge_root": str(self.knowledge_root), "error": None}
        except (OSError, ManifestError, LLMError, RuntimeError, ValueError) as exc:
            with self._lock:
                current = self._projects.get(self._active_project_id) if self._active_project_id else None
                self._error = str(exc)
                return {"available": False, "provider": self._provider_name, "model": self._model,
                        "selection": selection, "project": current["name"] if current else None,
                        "project_path": current["path"] if current else None, "projects_root": str(self.projects_root),
                        "knowledge_root": str(self.knowledge_root), "error": self._error}

    def _register_memory_tool(self, conversation_id=None, source_event_id=None):
        from laew.memory.tool import MemoryTool
        if self._agent is None:
            return
        self._agent.tools.pop("MemoryTool", None)
        self._executor._system_prompt_cache = None
        try:
            memory = self.memory()
            if memory is not None:
                self._agent.register_tool(MemoryTool(memory, self._active_project_id,
                                                     conversation_id, source_event_id))
        except Exception:
            logging.getLogger(__name__).debug("Memory tool unavailable")

    def chat(self, message: str, selection: object = "manifest", expected_project_id: object = _UNSPECIFIED_SCOPE) -> tuple[int, dict[str, Any]]:
        if not isinstance(message, str) or not message.strip():
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "A non-empty message is required."}
        try:
            with self._lock:
                if expected_project_id is not _UNSPECIFIED_SCOPE and expected_project_id != self._active_project_id:
                    return HTTPStatus.CONFLICT, {"error": "The active project changed before this message started. Review the selected project and retry."}
                self._ensure_runtime(selection)
                assert self._executor is not None
                self._register_memory_tool()
                from laew.knowledge.routing import KnowledgeTurn
                turn = KnowledgeTurn(lambda tool, op, args: self._call_tool(tool, op, args, None))
                turn.prepare(self._executor, message.strip(), self._active_project_id, self.memory,
                             self._agent.tools.get("RagTool") if self._agent else None)
                result = self._executor.run(message.strip(), stream=False, on_tool_call=turn.call,
                                            on_diagnostic=turn.observe, on_tool_batch=turn.after_tools)
            steps = [
                {"number": step.step_number, "tool": step.tool_name, "operation": step.operation, "call_id": step.call_id,
                 "success": None if step.tool_result is None else step.tool_result.success,
                 "error": None if step.tool_result is None else step.tool_result.error_message,
                 "sources": (step.tool_result.data or {}).get("sources", [])
                 if step.tool_result and isinstance(step.tool_result.data, dict) else []}
                for step in result.steps if step.tool_name or step.response
            ]
            if not result.success:
                return HTTPStatus.BAD_GATEWAY, {"error": result.error or "The Chief Agent did not complete the run.", "steps": steps}
            return HTTPStatus.OK, {"response": result.final_response, "provider": self._provider_name,
                                   "model": self._model, "steps": steps, "routing": turn.diagnostics,
                                   "usage": {"prompt_tokens": result.prompt_tokens,
                                             "completion_tokens": result.completion_tokens,
                                             "total_tokens": result.total_tokens}}
        except (OSError, ManifestError, LLMError, RuntimeError, ValueError) as exc:
            self._error = str(exc)
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": self._error}

    def stream_chat(
        self, message, selection, expected_project_id, emit, session_id=None,
        cancellation=None, model=None, account_id=None, conversation_id=None,
    ):
        if conversation_id is None:
            return self._stream_chat(message, selection, expected_project_id, emit, session_id,
                                     cancellation, model, account_id)
        from laew.console.session_store import SessionStoreError, _redact_conversation_value
        if not isinstance(message, str) or not message.strip():
            emit({"type": "error", "error": "A non-empty message is required."})
            return
        try:
            store = self.conversation_store()
            with store.conversation_run(conversation_id):
                conversation = store.load_conversation(conversation_id)
                if (conversation["project_id"] != self._active_project_id
                        or expected_project_id != conversation["project_id"]):
                    emit({"type": "error", "error": "Conversation scope does not match the active scope."})
                    return
                try: self.knowledge().baseline(conversation)
                except Exception: logging.getLogger(__name__).exception('Knowledge enrollment failed')
                try: self.memory().baseline(conversation)
                except Exception: logging.getLogger(__name__).exception('Memory enrollment failed')
                store.recover_interrupted_runs(conversation_id)
                history = store.conversation_messages(conversation_id)
                run_id = uuid.uuid4().hex
                user_event_id = uuid.uuid4().hex
                def persist(event):
                    store.append_conversation_event(conversation_id, {**event, "run_id": run_id})
                persist({"id": uuid.uuid4().hex, "kind": "run", "status": "running", "content": "",
                         "user_event_id": user_event_id})
                from laew.llm.base import LLMMessage, MessageRole
                user_message = LLMMessage(MessageRole.USER, message.strip())
                persist({"id": user_event_id, "kind": "user", "status": "completed",
                         "content": user_message.content, "message": user_message.to_dict()})
                first_user = {"pending": True}
                assistant_event_id = None
                def persist_agent_event(event):
                    nonlocal assistant_event_id
                    if first_user["pending"] and event.get("kind") == "user" and not event.get("generated"):
                        first_user["pending"] = False
                        return
                    persist(event)
                    if event.get("kind") == "assistant":
                        assistant_event_id = event["id"]
                state = {"status": "failed", "finalized": False}
                diagnostics = {"version": 1, "routing": None, "requests": [], "tools": []}
                checkpointed = False
                def capture(phase, snapshot):
                    nonlocal diagnostics, checkpointed
                    diagnostics = _redact_conversation_value(snapshot)
                    if phase == "provider_request" and not checkpointed:
                        store.checkpoint_turn(conversation_id, run_id, diagnostics)
                        checkpointed = True
                    send({"type": "diagnostics", "phase": phase, "diagnostics": diagnostics})
                def finalize(status, reason=""):
                    persist({"id": uuid.uuid4().hex, "kind": "run", "status": status, "content": reason,
                             "user_event_id": user_event_id, "diagnostics": diagnostics,
                             "assistant_event_id": assistant_event_id if status == "completed" else None})
                    state.update(status=status, finalized=True)
                def send(event):
                    if event.get("type") == "done":
                        finalize("completed")
                        try:
                            self.knowledge().enqueue(store.load_conversation(conversation_id),
                                self.knowledge_selection(expected_project_id))
                            self._knowledge_worker.request()
                        except Exception:
                            logging.getLogger(__name__).exception('Knowledge analysis could not be scheduled')
                        try:
                            memory=self.memory()
                            memory.enqueue(store.load_conversation(conversation_id),self.memory_selection())
                            self._memory_worker.request()
                        except Exception:
                            logging.getLogger(__name__).exception("Memory extraction could not be scheduled")
                    elif event.get("type") == "error":
                        status = "cancelled" if cancellation and cancellation.is_set() else "failed"
                        reason = _redact_conversation_value(str(event.get("error") or "Run failed."))
                        finalize(status, reason)
                        event = {**event, "type": "cancelled" if status == "cancelled" else "error",
                                 "error": reason}
                    emit({**event, "run_id": run_id, "conversation_id": conversation_id,
                          **({"diagnostics": diagnostics, "run_status": state["status"]}
                             if state["finalized"] else {})})
                try:
                    send({"type": "diagnostics", "phase": "starting", "diagnostics": diagnostics})
                    self._stream_chat(message, selection, expected_project_id, send, session_id,
                                      cancellation, model, account_id, conversation_id,
                                      history, persist_agent_event, user_event_id, capture)
                except StreamCancelled:
                    if not state["finalized"]:
                        finalize("cancelled", "Response cancelled.")
                        if cancellation and cancellation.is_set():
                            emit({"type": "cancelled", "conversation_id": conversation_id, "run_id": run_id,
                                  "run_status": "cancelled", "diagnostics": diagnostics})
                finally:
                    if not state["finalized"]:
                        finalize("cancelled" if cancellation and cancellation.is_set() else state["status"])
        except (SessionStoreError, FileNotFoundError, OSError, ValueError) as exc:
            emit({"type": "error", "error": str(exc)})

    def _stream_chat(
        self,
        message: str,
        selection: object,
        expected_project_id: Optional[str],
        emit,
        session_id: Optional[str] = None,
        cancellation=None,
        model=None,
        account_id=None,
        conversation_id=None,
        stored_history=None,
        on_event=None,
        source_event_id=None,
        on_diagnostic=None,
    ) -> None:
        """Run the existing Chief Agent and emit newline-delimited events."""
        original_emit = emit
        def emit(event):
            if cancellation and cancellation.is_set():
                raise StreamCancelled()
            original_emit(event)
        if not isinstance(message, str) or not message.strip():
            emit({"type": "error", "error": "A non-empty message is required."})
            return
        try:
            with self._lock:
                if expected_project_id is not _UNSPECIFIED_SCOPE and expected_project_id != self._active_project_id:
                    emit({
                        "type": "error",
                        "error": "The active project changed before this message started. Review the selected project and retry.",
                    })
                    return
                self._activate_session(session_id, conversation_id) if conversation_id else self._activate_session(session_id)
                if selection in CLOUD_PROVIDERS or model is not None:
                    self._ensure_runtime(selection, model, account_id)
                else:
                    self._ensure_runtime(selection)
                assert self._executor is not None
                if stored_history is not None:
                    self._agent.history = stored_history
                emit({
                    "type": "start", "provider": self._provider_name,
                    "model": self._model,
                })
                try:
                    from laew.knowledge.tool import KnowledgeProposalTool
                    self._agent.tools.pop('KnowledgeProposalTool', None)
                    self._executor._system_prompt_cache = None
                    self._agent.register_tool(KnowledgeProposalTool(self.knowledge(), self._active_project_id,
                        conversation_id, source_event_id))
                except Exception:
                    logging.getLogger(__name__).exception('Knowledge proposal tool unavailable')
                self._register_memory_tool(conversation_id, source_event_id)
                from laew.knowledge.routing import KnowledgeTurn
                def routing_event(diagnostics):
                    if on_diagnostic is not None:
                        on_diagnostic("context_preparation", turn.snapshot())
                        if cancellation and cancellation.is_set():
                            raise StreamCancelled()
                    else:
                        emit({"type": "routing", "routing": diagnostics})
                turn = KnowledgeTurn(
                    lambda tool, op, args: self._call_tool_checked(tool, op, args, emit, session_id, cancellation),
                    notify=routing_event,
                )
                used_memories = turn.prepare(self._executor, message.strip(), self._active_project_id,
                                             self.memory, self._agent.tools.get("RagTool") if self._agent else None)
                if on_diagnostic is None:
                    emit({"type": "memory", "memories": used_memories, "mode": turn.diagnostics["memory"]})
                run_options = {"cancellation": cancellation} if cancellation is not None else {}
                if on_event is not None:
                    run_options["on_event"] = on_event
                def observe(phase, details):
                    turn.observe(phase, details)
                    if on_diagnostic is not None:
                        on_diagnostic(phase, turn.snapshot())
                    elif phase == "provider_dispatch":
                        routing_event(turn.snapshot()["routing"])
                run_options["on_diagnostic"] = observe
                result = self._executor.run(
                    message.strip(), stream=True,
                    on_delta=lambda text: emit(
                        {"type": "reset"} if text is None else {"type": "delta", "text": text}
                    ),
                    on_step=lambda step: emit({"type": "step", "step": {
                        "number": step.step_number, "tool": step.tool_name,
                        "operation": step.operation, "call_id": step.call_id,
                        "success": None if step.tool_result is None else step.tool_result.success,
                        "error": None if step.tool_result is None else step.tool_result.error_message,
                        "sources": (step.tool_result.data or {}).get("sources", [])
                        if step.tool_result and isinstance(step.tool_result.data, dict) else [],
                    }}),
                    on_tool_call=turn.call,
                    on_tool_batch=turn.after_tools,
                    **run_options,
                )
            steps = [
                {"number": step.step_number, "tool": step.tool_name,
                 "operation": step.operation, "call_id": step.call_id,
                 "success": None if step.tool_result is None else step.tool_result.success,
                 "error": None if step.tool_result is None else step.tool_result.error_message,
                 "sources": (step.tool_result.data or {}).get("sources", [])
                 if step.tool_result and isinstance(step.tool_result.data, dict) else []}
                for step in result.steps if step.tool_name or step.response
            ]
            if not result.success:
                emit({"type": "error", "error": result.error or "The Chief Agent did not complete the run.", "steps": steps})
                return
            emit({
                "type": "done", "response": result.final_response,
                "provider": self._provider_name, "model": self._model,
                "steps": steps,
                **({"routing": turn.diagnostics} if on_diagnostic is None else {}),
                "usage": {"prompt_tokens": result.prompt_tokens,
                          "completion_tokens": result.completion_tokens,
                          "total_tokens": result.total_tokens},
            })
        except StreamCancelled:
            if on_diagnostic is not None:
                raise
            return
        except (OSError, ManifestError, LLMError, RuntimeError, ValueError) as exc:
            self._error = str(exc)
            emit({"type": "error", "error": self._error})

    def _call_tool_checked(self, tool, operation, args, emit, session_id, cancellation):
        if cancellation and cancellation.is_set():
            raise StreamCancelled()
        return self._call_tool(tool, operation, args, emit, session_id, cancellation)


def make_handler(service: WorkspaceService):
    """Create a same-origin-only request handler bound to *service*."""
    static_root = Path(__file__).with_name("ui")
    # A running backend must not start serving a newer frontend after an edit.
    assets = {
        name: (static_root / name).read_bytes()
        for name in ("index.html", "app.js", "app.css", "markdown.js", "stream.js",
                     "theme.js", "ui-state.js", "settings.js", "knowledge.js")
    }

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

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
            if not self._local_host(): return
            parsed = urlparse(self.path)
            if parsed.path == "/api/knowledge/state":
                params=parse_qs(parsed.query)
                status,data=service.knowledge_request('state',{key:values[0] for key,values in params.items()})
                self._json(status,data); return
            if parsed.path in {"/api/memory/state", "/api/memory/get"}:
                params=parse_qs(parsed.query)
                status,data=service.memory_request(parsed.path.rsplit('/',1)[-1],{key:values[0] for key,values in params.items()})
                self._json(status,data); return
            if parsed.path == "/api/settings":
                status,data=service.application_settings(); self._json(status,data); return
            if parsed.path in {"/api/conversations", "/api/conversation"}:
                from laew.console.session_store import SessionStoreError
                try:
                    store = service.conversation_store()
                    if parsed.path == "/api/conversations":
                        self._json(HTTPStatus.OK, {"conversations": store.list_conversations()})
                    else:
                        params = parse_qs(parsed.query)
                        self._json(HTTPStatus.OK, service.read_conversation(
                            params.get("id", [""])[0], params.get("project_id", [None])[0]))
                except PermissionError as exc:
                    self._json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
                except (SessionStoreError, OSError, ValueError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            if parsed.path in {"/api/cloud/status", "/api/cloud/models", "/api/cloud/history"}:
                params = parse_qs(parsed.query, keep_blank_values=True)
                status, data = service.cloud_request(parsed.path, {key: value[0] for key, value in params.items()})
                self._json(status, data); return
            if parsed.path == "/api/projects":
                self._json(HTTPStatus.OK, service.list_projects()); return
            if parsed.path == "/api/status":
                params = parse_qs(parsed.query)
                selection = params.get("provider", ["manifest"])[0]
                self._json(HTTPStatus.OK, service.status(selection, params.get("model", [None])[0],
                                                       params.get("session_id", [None])[0])); return
            if parsed.path == "/api/rag":
                self._json(HTTPStatus.OK, service.sync_status()); return
            if parsed.path == "/api/project/settings":
                status, response = service.project_settings()
                self._json(status, response); return
            requested = "index.html" if parsed.path in ("/", "/index.html") else parsed.path.lstrip("/")
            if requested not in assets:
                self.send_error(HTTPStatus.NOT_FOUND); return
            data = assets[requested]
            content_type = "text/html" if requested.endswith("html") else ("text/css" if requested.endswith("css") else "application/javascript")
            self.send_response(HTTPStatus.OK); self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

        def do_POST(self) -> None:
            if not self._local_host(): return
            route = urlparse(self.path).path
            if route not in {"/api/knowledge/settings", "/api/knowledge/analyze", "/api/knowledge/preview", "/api/knowledge/edit", "/api/knowledge/decide", "/api/knowledge/sync", "/api/settings", "/api/project/config", "/api/memory/settings", "/api/memory/add", "/api/memory/update", "/api/memory/delete", "/api/memory/decide", "/api/memory/analyze", "/api/memory/sync", "/api/memory/rebuild", "/api/chat", "/api/chat/cancel", "/api/project", "/api/projects", "/api/rag/sync", "/api/project/settings", "/api/approval", "/api/project/permissions", "/api/cloud/new", "/api/cloud/key", "/api/cloud/auth/start", "/api/cloud/auth/cancel", "/api/cloud/auth/logout", "/api/conversations", "/api/conversation/rename", "/api/conversation/delete"}:
                self.send_error(HTTPStatus.NOT_FOUND); return
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if origin and origin not in {f"http://{host}", f"http://127.0.0.1:{host.rsplit(':', 1)[-1]}"}:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Cross-origin requests are not allowed."}); return
            if (route == "/api/cloud/key" or route.startswith("/api/knowledge/")) and (not origin or self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
                self._json(HTTPStatus.FORBIDDEN, {"error": "This operation requires a same-origin JSON request."}); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1_000_000: raise ValueError("Message is too large.")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON request."}); return
            if not isinstance(body, dict):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be a JSON object."}); return
            if route.startswith('/api/knowledge/'):
                status,data=service.knowledge_request(route.rsplit('/',1)[-1],body); self._json(status,data); return
            if route.startswith('/api/memory/'):
                status,data=service.memory_request(route.rsplit('/',1)[-1],body); self._json(status,data); return
            if route in {'/api/settings','/api/project/config'}:
                status,data=service.application_settings(body); self._json(status,data); return
            if route in {"/api/conversations", "/api/conversation/rename", "/api/conversation/delete"}:
                from laew.console.session_store import SessionStoreError
                try:
                    store = service.conversation_store()
                    if route == "/api/conversations":
                        result = service.create_conversation(body.get("scope_type"), body.get("project_id"))
                    elif route.endswith("rename"):
                        result = store.rename_conversation(body.get("id"), body.get("title"))
                    else:
                        result = {"deleted": store.delete_conversation(body.get("id"))}
                    self._json(HTTPStatus.OK, result)
                except (SessionStoreError, OSError, ValueError, TypeError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            if route.startswith("/api/cloud/"):
                status, data = service.cloud_request(route, body)
                self._json(status, data); return
            if route == "/api/chat/cancel":
                accepted = service.cancel_run(body.get("session_id"), body.get("run_id"))
                self._json(HTTPStatus.OK if accepted else HTTPStatus.BAD_REQUEST, {"accepted": accepted}); return
            if route == "/api/projects":
                status, response = service.create_project(body.get("name"))
                self._json(status, response); return
            if route == "/api/project":
                status, response = service.select_project(body.get("project_id"))
                self._json(status, response); return
            if route == "/api/rag/sync":
                status, response = service.request_sync(body.get("scope"))
                self._json(status, response); return
            if route == "/api/project/settings":
                status, response = service.update_project_settings(body.get("project_id"), body.get("documentation_language"))
                self._json(status, response); return
            if route == "/api/project/permissions":
                status, response = service.update_permission_mode(body.get("project_id"), body.get("permission_mode"))
                self._json(status, response); return
            if route == "/api/approval":
                broker = service._permissions
                accepted = broker is not None and broker.decide(body.get("id"), body.get("decision"), body.get("session_id"))
                self._json(HTTPStatus.OK if accepted else HTTPStatus.CONFLICT,
                           {"accepted": accepted}); return
            if (isinstance(body.get("provider"), str) and body["provider"] in CLOUD_PROVIDERS
                    and service._run_key(body.get("session_id"), body.get("run_id")) is None):
                self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Cloud Chat requires valid session and run IDs for Stop."}); return
            try:
                cancellation = service.register_run(body.get("session_id"), body.get("run_id"))
            except ValueError:
                self._json(HTTPStatus.CONFLICT, {"error": "Run ID is already active."}); return
            try:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Cache-Control", "no-store, no-transform")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError, OSError):
                if cancellation is not None:
                    service.unregister_run(body.get("session_id"), body.get("run_id"), cancellation)
                return

            def emit(event: dict[str, Any]) -> None:
                payload = json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n"
                try:
                    self.wfile.write(f"{len(payload):X}\r\n".encode("ascii"))
                    self.wfile.write(payload + b"\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                    raise StreamCancelled() from exc

            try:
                service.stream_chat(
                    body.get("message"), body.get("provider", "manifest"),
                    body.get("project_id", _UNSPECIFIED_SCOPE), emit, body.get("session_id"), cancellation,
                    **({"model": body.get("model"), "account_id": body.get("account_id")}
                       if body.get("model") is not None or body.get("provider") in CLOUD_PROVIDERS else {}),
                    **({"conversation_id": body["conversation_id"]} if "conversation_id" in body else {}),
                )
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError, StreamCancelled):
                return
            finally:
                if cancellation is not None:
                    if cancellation.is_set():
                        self.close_connection = True
                    service.unregister_run(body.get("session_id"), body.get("run_id"), cancellation)

        def _local_host(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Use the loopback Workbench address."})
                return False
            return True

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
    service.start_sync()
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"LAEW UI listening on {url} (loopback only). Press Ctrl+C to stop.")
    if open_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        service.close()
