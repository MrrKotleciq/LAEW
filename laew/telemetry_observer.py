"""Project agent diagnostics into a content-free telemetry trace."""

from __future__ import annotations

import time
from uuid import uuid4

from laew.agent.executor import StreamCancelled
from laew.tools.base import ErrorCode


_ERRORS = {
    "ERR_INVALID_INPUT": "validation",
    "ERR_INVALID_OPERATION": "validation",
    "ERR_UNAUTHORIZED": "permission_denied",
    "ERR_PATH_DENIED": "permission_denied",
    "ERR_PATH_OUT_OF_BOUNDS": "permission_denied",
    "ERR_COMMAND_BLOCKED": "permission_denied",
    "ERR_TIMEOUT": "timeout",
    "ERR_CANCELLED": "cancelled",
    "ERR_AGENT_EXECUTION": "internal_error",
    "ERR_RAG_FAILURE": "dependency_unavailable",
    "ERR_MEMORY_UNAVAILABLE": "dependency_unavailable",
    "TimeoutError": "timeout",
    "PermissionError": "permission_denied",
    "OSError": "io_error",
    "StreamCancelled": "cancelled",
}
_ROUTES = {
    (False, False): "none",
    (True, False): "project",
    (False, True): "global",
    (True, True): "both",
}
_PROVIDERS = {"OllamaProvider": "ollama", "LlamaCppProvider": "llamacpp", "GeminiProvider": "gemini"}


def provider_label(provider, selection=None):
    """Resolve a built-in provider label without recording model or account IDs."""
    built_in = _PROVIDERS.get(type(provider).__name__)
    if built_in is not None:
        return built_in
    if type(selection) is str and selection in {"openai-api", "chatgpt", "gemini", "ollama", "llama.cpp"}:
        return "llamacpp" if selection == "llama.cpp" else selection
    return "unknown"


def _error_code(value):
    if isinstance(value, ErrorCode):
        value = value.value
    if type(value) is str:
        # Executor callbacks may carry str(ErrorCode) on Python versions on
        # which it includes the enum name.
        return _ERRORS.get(value.removeprefix("ErrorCode."), "unknown")
    return "unknown"


def _usage(usage):
    usage = usage if type(usage) is dict else {}
    counts = {}
    for kind in ("input", "output", "total"):
        value = usage.get(kind)
        known = type(value) is int and 0 <= value <= 2**53
        counts[f"{kind}_tokens"] = value if known else None
        counts[f"{kind}_source"] = "reported" if known else "unavailable"
    return counts


def observe_generation(run, provider, generate, *args, **kwargs):
    """Instrument one direct provider invocation at its owning call site."""
    if run is None:
        return generate(*args, **kwargs)
    span_id = str(uuid4())
    started = time.perf_counter()
    run.emit("llm.started", status="started", span_id=span_id,
             parent_span_id=run.span_id, provider=provider, attempt=1)
    status, error, usage = "failed", "internal_error", {}
    try:
        response = generate(*args, **kwargs)
        usage = {"input": getattr(response, "prompt_tokens", None),
                 "output": getattr(response, "completion_tokens", None),
                 "total": getattr(response, "total_tokens", None)}
        status, error = "completed", None
        return response
    except (StreamCancelled, KeyboardInterrupt):
        status, error = "cancelled", "cancelled"
        raise
    except Exception as exc:
        error = _error_code(type(exc).__name__)
        raise
    finally:
        run.emit("llm.finished", status=status, span_id=span_id, parent_span_id=run.span_id,
                 provider=provider, attempt=1, error_code=error,
                 duration_ms=(time.perf_counter() - started) * 1000, **_usage(usage))


class ExecutionObserver:
    """One adapter per agent invocation. Correlation keys stay in memory."""

    def __init__(self, run, *, provider="unknown", role="primary", parent_span_id=None):
        self.run = run
        self.provider = "llamacpp" if provider == "llama.cpp" else provider
        self.role = role
        self.parent_span_id = parent_span_id or run.span_id
        self.span_id = str(uuid4())
        self._route = None
        self._provider_span = None
        self._provider_attempt = None
        self._attempt_provider = self.provider
        self._provider_dispatched = False
        self._tool_span = None
        self._tool_order = None

    def routing(self, diagnostics):
        scopes = diagnostics.get("scopes") if type(diagnostics) is dict else None
        if type(scopes) not in (list, tuple):
            return
        project = any(type(scope) is str and scope == "project" for scope in scopes)
        global_ = any(type(scope) is str and scope == "global" for scope in scopes)
        route = _ROUTES[project, global_]
        if route != self._route:
            self._route = route
            self.run.emit("routing.decided", span_id=self.parent_span_id,
                          route=route, enabled=project or global_)

    def observe(self, phase, details, provider=None):
        if type(details) is not dict:
            return
        if phase == "provider_request":
            self._provider_span = str(uuid4())
            self._provider_attempt = details.get("attempt")
            self._provider_dispatched = False
            self._attempt_provider = provider_label(provider, self.provider) if provider is not None else self.provider
            self.run.emit("llm.started", status="started", span_id=self._provider_span,
                          parent_span_id=self.span_id, provider=self._attempt_provider,
                          attempt=self._provider_attempt)
        elif phase == "provider_dispatch" and self._provider_span is not None:
            self._provider_dispatched = True
        elif phase == "provider_outcome" and self._provider_span is not None:
            status = details.get("status")
            self.run.emit("llm.finished", status=status, span_id=self._provider_span,
                          parent_span_id=self.span_id, provider=self._attempt_provider,
                          attempt=self._provider_attempt, dispatched=self._provider_dispatched,
                          error_code=_error_code(details.get("error_category")) if status != "completed" else None,
                          duration_ms=details.get("elapsed_ms"), **_usage(details.get("usage")))
            self._provider_span = None
        elif phase == "tool_started":
            self._tool_span = str(uuid4())
            self._tool_order = details.get("order")
            self.run.emit("tool.started", status="started", span_id=self._tool_span,
                          parent_span_id=self.span_id, tool=details.get("tool"),
                          operation=details.get("operation"))
        elif phase == "tool" and self._tool_span is not None and details.get("order") == self._tool_order:
            status = details.get("status")
            denied = status == "denied"
            executed = details.get("executed") is True
            reused = details.get("reused") is True
            decision = "denied" if denied else "allowed" if executed and status != "cancelled" else "unknown"
            self.run.emit("tool.finished", status="failed" if denied else status,
                          error_code="permission_denied" if denied else (
                              _error_code(details.get("error_category")) if status != "completed" else None
                          ), span_id=self._tool_span, parent_span_id=self.span_id,
                          tool=details.get("tool"), operation=details.get("operation"),
                          decision=decision, executed=executed and not denied, reused=reused,
                          duration_ms=details.get("elapsed_ms"))
            self._tool_span = None

    def execute(self, executor, message, *, on_diagnostic=None, **options):
        def diagnostic(phase, details):
            if phase != "tool":
                provider = None
                if phase == "provider_request":
                    try:
                        provider = getattr(getattr(executor, "agent", None), "provider", None)
                    except (IndexError, AttributeError):
                        pass
                self.observe(phase, details, provider)
            if on_diagnostic is not None:
                on_diagnostic(phase, details)
            if phase == "tool":
                self.observe(phase, details)

        started = time.perf_counter()
        self.run.emit("agent.started", status="started", span_id=self.span_id,
                      parent_span_id=self.parent_span_id, role=self.role)
        status, error = "failed", "internal_error"
        try:
            result = executor.run(message, on_diagnostic=diagnostic, **options)
            cancellation = options.get("cancellation")
            if result.success:
                status, error = "completed", None
            elif cancellation is not None and cancellation.is_set():
                status, error = "cancelled", "cancelled"
            return result
        except (StreamCancelled, KeyboardInterrupt):
            status, error = "cancelled", "cancelled"
            raise
        finally:
            self.run.emit("agent.finished", status=status, error_code=error, span_id=self.span_id,
                          parent_span_id=self.parent_span_id, role=self.role,
                          duration_ms=(time.perf_counter() - started) * 1000)


class _SafeTrace:
    """Do not let an injected diagnostic sink alter an application result."""

    def __init__(self, run):
        self._run = run
        self.span_id = run.span_id

    def emit(self, *args, **kwargs):
        try:
            self._run.emit(*args, **kwargs)
        except Exception:
            pass

    def finish(self, *args, **kwargs):
        self._run.finish(*args, **kwargs)


def start_observed_run(sink, surface, scope="none"):
    """Start a trace through the verified or explicitly injected sink."""
    if sink is None:
        return None
    try:
        return _SafeTrace(sink.start_run(surface, scope))
    except Exception:
        return None


def finish_observed_run(run, status, error=None):
    if run is not None:
        try:
            run.finish(status, error)
        except Exception:
            pass


def execute_observed_turn(executor, message, *, sink, scope, routing, on_diagnostic, surface="cli_chat", run=None, **options):
    """Wrap an admitted agent invocation while preserving its diagnostics."""
    owns_run = run is None
    if owns_run:
        run = start_observed_run(sink, surface, scope)
    if run is None:
        return executor.run(message, on_diagnostic=on_diagnostic, **options)
    observer = ExecutionObserver(run)
    status, error = "failed", "internal_error"
    try:
        observer.routing(routing)
        def diagnostic(phase, details):
            if on_diagnostic is not None:
                on_diagnostic(phase, details)
            observer.routing(routing)
        result = observer.execute(executor, message, on_diagnostic=diagnostic, **options)
        if result.success:
            status, error = "completed", None
        return result
    except (KeyboardInterrupt, StreamCancelled):
        status, error = "cancelled", "cancelled"
        raise
    finally:
        if owns_run:
            finish_observed_run(run, status, error)
