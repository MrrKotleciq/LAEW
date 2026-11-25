import json
from types import SimpleNamespace

import pytest

from laew.telemetry_observer import execute_observed_turn
from laew.telemetry import TelemetrySink
from laew.tools.base import ErrorCode, ToolResult


def records(root):
    files = list(root.glob('*.jsonl'))
    assert len(files) == 1
    return [json.loads(line) for line in files[0].read_text().splitlines()]


class FakeExecutor:
    def __init__(self, outcome=True):
        self.outcome = outcome

    def run(self, message, *, on_diagnostic, **kwargs):
        on_diagnostic('provider_request', {'attempt': 1, 'text': message})
        on_diagnostic('provider_dispatch', {})
        on_diagnostic('provider_outcome', {'status': 'completed', 'elapsed_ms': 1,
                                          'usage': {'input': 2, 'output': 3, 'total': 5}})
        if self.outcome == 'cancel':
            raise KeyboardInterrupt()
        return SimpleNamespace(success=self.outcome)


def test_chat_trace_correlates_agent_and_provider_without_content(tmp_path):
    sink = TelemetrySink(tmp_path)
    diagnostic = []
    result = execute_observed_turn(FakeExecutor(), 'secret canary', sink=sink, scope='project',
                               routing={'scopes': ['project']},
                               on_diagnostic=lambda phase, details: diagnostic.append(phase))
    assert result.success
    events = records(tmp_path)
    assert [e['event'] for e in events] == ['run.started', 'routing.decided', 'agent.started',
                                             'llm.started', 'llm.finished', 'agent.finished', 'run.finished']
    assert events[-1]['status'] == 'completed'
    assert events[3]['parent_span_id'] == events[2]['span_id']
    assert 'secret canary' not in json.dumps(events)
    assert diagnostic == ['provider_request', 'provider_dispatch', 'provider_outcome']


@pytest.mark.parametrize('outcome,status', [(False, 'failed'), ('cancel', 'cancelled')])
def test_chat_terminal_on_failure_and_cancel(tmp_path, outcome, status):
    kwargs = dict(sink=TelemetrySink(tmp_path), scope='global', routing={}, on_diagnostic=lambda *_: None)
    if outcome == 'cancel':
        with pytest.raises(KeyboardInterrupt):
            execute_observed_turn(FakeExecutor(outcome), 'x', **kwargs)
    else:
        execute_observed_turn(FakeExecutor(outcome), 'x', **kwargs)
    assert records(tmp_path)[-1]['status'] == status


def test_unavailable_sink_keeps_execution_result():
    class Broken:
        def start_run(self, *args):
            raise OSError('secret')
    result = execute_observed_turn(FakeExecutor(), 'x', sink=Broken(), scope='global',
                               routing={}, on_diagnostic=lambda *_: None)
    assert result.success


def test_workflow_rollback_has_correlated_tool_spans(tmp_path):
    from laew.workflow.definition import WorkflowDefinition, WorkflowMode, WorkflowStep, StepType, RollbackConfig
    from laew.workflow.engine import WorkflowEngine
    from laew.workflow.exceptions import WorkflowExecutionError
    from laew.telemetry_observer import start_observed_run, finish_observed_run

    class Tool:
        name = 'FilesystemTool'
        def __init__(self): self.calls = []
        def call(self, operation, **kwargs):
            self.calls.append(operation)
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, 'private') if operation == 'list_dir' else ToolResult.ok()

    tool = Tool()
    rollback = RollbackConfig(type=StepType.TOOL, tool='filesystem', operation='delete_file')
    steps = [WorkflowStep('one', 'one', StepType.TOOL, tool='filesystem', operation='write_file',
                          arguments={'content': 'secret-canary'}, rollback=rollback),
             WorkflowStep('two', 'two', StepType.TOOL, tool='filesystem', operation='list_dir')]
    trace = start_observed_run(TelemetrySink(tmp_path), 'workflow')
    engine = WorkflowEngine(WorkflowDefinition('fixture', '', WorkflowMode.AUTOMATIC, steps),
                            tool_registry={'FilesystemTool': tool}, telemetry_run=trace)
    with pytest.raises(WorkflowExecutionError):
        engine.run()
    finish_observed_run(trace, 'failed', 'internal_error')
    assert tool.calls == ['write_file', 'list_dir', 'delete_file']
    events = records(tmp_path)
    assert [e['operation'] for e in events if e['event'] == 'tool.finished'] == tool.calls
    assert all(e['parent_span_id'] == events[0]['span_id'] for e in events if e['event'] == 'tool.finished')
    assert 'secret-canary' not in json.dumps(events)


def test_multiagent_synthesis_is_child_agent_span(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import laew.multiagent.coordinator as module
    from laew.telemetry_observer import start_observed_run, finish_observed_run
    trace = start_observed_run(TelemetrySink(tmp_path), 'multiagent')
    class Executor(FakeExecutor):
        def run(self, message, **kwargs):
            super().run(message, **kwargs)
            return SimpleNamespace(success=True, final_response='fixture result')
    monkeypatch.setattr(module, 'AgentExecutor', lambda agent: Executor())
    coordinator = module.MultiAgentCoordinator(chief=object(), agents={})
    coordinator.telemetry_run = trace
    assert coordinator._synthesize_final_answer(MagicMock(render=lambda *a: 'private context'),
                                                SimpleNamespace(objective='private objective')) == 'fixture result'
    finish_observed_run(trace, 'completed')
    events = records(tmp_path)
    assert [e['event'] for e in events] == ['run.started', 'agent.started', 'llm.started',
                                             'llm.finished', 'agent.finished', 'run.finished']
    assert events[1]['role'] == 'coordinator'
    assert 'private objective' not in json.dumps(events)


def test_console_agent_uses_one_synthetic_trace(tmp_path, monkeypatch):
    import laew.agent.executor as executor_module
    import laew.console.commands.agent as command
    from laew.console.state import SessionState
    fs = SimpleNamespace(resolver=SimpleNamespace(project_root=tmp_path))
    agent = SimpleNamespace(tools={'FilesystemTool': fs})
    monkeypatch.setattr(command, '_build_agent', lambda state: (agent, 'fixture'))
    monkeypatch.setattr('laew.console.permissions.console_broker', lambda *a: object())
    class Executor(FakeExecutor):
        def __init__(self, agent): super().__init__()
        def run(self, message, **kwargs):
            super().run(message, **kwargs)
            return SimpleNamespace(success=True, final_response='ok', total_steps=1,
                                   prompt_tokens=2, completion_tokens=3)
    monkeypatch.setattr(executor_module, 'AgentExecutor', Executor)
    state = SessionState(trace=False)
    state._telemetry_sink = TelemetrySink(tmp_path)
    assert command.cmd_agent_run(['private prompt'], state) == 0
    events = records(tmp_path)
    assert events[0]['surface'] == 'console'
    assert events[-1]['status'] == 'completed'
    assert 'private prompt' not in json.dumps(events)
    assert state.conversation[0]['content'] == 'private prompt'
