"""Content-free instrumentation for directly dispatched workflow steps."""
from time import perf_counter
from uuid import uuid4

from laew.telemetry_observer import ExecutionObserver, _error_code


def call_tool(run, tool, operation, arguments):
    if run is None:
        return tool.call(operation, **arguments)
    span, started = str(uuid4()), perf_counter()
    run.emit('tool.started', status='started', span_id=span, parent_span_id=run.span_id,
             tool=tool.name, operation=operation)
    status, error = 'failed', 'internal_error'
    try:
        result = tool.call(operation, **arguments)
        status = 'completed' if result.success else 'failed'
        error = None if result.success else _error_code(result.error_code)
        return result
    except KeyboardInterrupt:
        status, error = 'cancelled', 'cancelled'
        raise
    finally:
        run.emit('tool.finished', status=status, error_code=error, span_id=span,
                 parent_span_id=run.span_id, tool=tool.name, operation=operation,
                 decision='unknown', executed=True, reused=False,
                 duration_ms=(perf_counter() - started) * 1000)


def call_agent(run, executor, prompt):
    if run is None:
        return executor.run(prompt)
    return ExecutionObserver(run).execute(executor, prompt)
