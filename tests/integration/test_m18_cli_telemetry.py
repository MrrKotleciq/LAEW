import json
from argparse import Namespace
from types import SimpleNamespace

import pytest

from laew.cli import cmd_tool
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


def test_standalone_denial_records_no_arguments(tmp_path, monkeypatch):
    from laew.console import permissions
    monkeypatch.setattr(permissions, 'console_call', lambda *args: ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, 'secret'))
    args = Namespace(tool='filesystem', operation='write_file', args=['content=secret-canary'],
                     log=None, manifest=str(tmp_path / 'absent'), require_approval=True,
                     _telemetry_sink=TelemetrySink(tmp_path))
    assert cmd_tool(args) == 1
    events = records(tmp_path)
    assert [e['event'] for e in events] == ['run.started', 'tool.started', 'tool.finished', 'run.finished']
    assert events[2]['decision'] == 'denied'
    assert 'executed' not in events[2]
    assert events[-1]['status'] == 'failed'
    assert 'secret-canary' not in json.dumps(events)


def test_no_persist_never_starts_injected_sink(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import laew.cli as cli
    (tmp_path / 'Projects').mkdir()
    (tmp_path / 'Knowledge').mkdir()
    sink = MagicMock()
    provider = MagicMock(base_url='fixture')
    monkeypatch.setattr(cli, 'load_manifest', lambda *_: {})
    monkeypatch.setattr(cli, 'build_provider_for_role', lambda *a, **k: provider)
    monkeypatch.setattr(cli, 'resolve_model_name', lambda *a, **k: 'fixture')
    monkeypatch.setattr(cli, 'build_shared_tools', lambda *a, **k: [])
    monkeypatch.setattr('laew.memory.integration.build_memory', MagicMock(side_effect=RuntimeError()))
    monkeypatch.setattr('builtins.input', MagicMock(side_effect=['hello', 'exit']))
    args = Namespace(general=True, workspace_root=str(tmp_path), model=None, base_url=None,
                     timeout=None, provider=None, manifest='manifest.yaml', resume=None,
                     session=None, no_persist=True, no_stream=True, _telemetry_sink=sink)
    # Provide the result attributes used by the CLI presentation.
    class Executor(FakeExecutor):
        def run(self, message, **kwargs):
            return SimpleNamespace(success=True, final_response='ok', total_tokens=0)
    monkeypatch.setattr(cli, 'AgentExecutor', lambda agent: Executor())
    assert cli.cmd_chat(args) == 0
    sink.start_run.assert_not_called()


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

@pytest.mark.parametrize('failure,expected', [('prepare', 'failed'), ('storage', 'failed'), ('cancel', 'cancelled'), (None, 'completed')])
def test_chat_root_covers_preparation_and_conversation_storage(tmp_path, monkeypatch, failure, expected):
    from unittest.mock import MagicMock
    import laew.cli as cli
    from laew.console.session_store import SessionStoreError
    from laew.knowledge.routing import KnowledgeTurn

    (tmp_path / 'Projects').mkdir()
    (tmp_path / 'Knowledge').mkdir()
    (tmp_path / 'telemetry').mkdir()
    sink = TelemetrySink(tmp_path / 'telemetry')
    provider = MagicMock(base_url='fixture')
    store = MagicMock()
    store.create_conversation.return_value = {'id': 'conversation'}
    store.conversation_messages.return_value = []
    def append(_id, event):
        if failure == 'storage' and event.get('kind') == 'run' and event.get('status') == 'completed':
            raise SessionStoreError('storage failure')
    store.append_conversation_event.side_effect = append
    monkeypatch.setattr(cli, 'load_manifest', lambda *_: {})
    monkeypatch.setattr(cli, 'build_provider_for_role', lambda *a, **k: provider)
    monkeypatch.setattr(cli, 'resolve_model_name', lambda *a, **k: 'fixture')
    monkeypatch.setattr(cli, 'build_shared_tools', lambda *a, **k: [])
    monkeypatch.setattr(cli, 'session_store_from_manifest', lambda *_: MagicMock())
    monkeypatch.setattr('laew.console.session_store.conversation_store_from_manifest', lambda *a: store)
    monkeypatch.setattr('laew.memory.integration.build_memory', MagicMock(side_effect=RuntimeError()))
    monkeypatch.setattr('builtins.input', MagicMock(side_effect=['hello', 'exit']))
    def prepare(*args):
        if failure == 'prepare':
            raise RuntimeError('private preparation error')
        if failure == 'cancel':
            raise KeyboardInterrupt()
        args[0].diagnostics.update(memory_requested=False, prefetch=[])
    monkeypatch.setattr(KnowledgeTurn, 'prepare', prepare)
    class Executor(FakeExecutor):
        def run(self, message, **kwargs):
            return SimpleNamespace(success=True, final_response='ok', total_tokens=0)
    monkeypatch.setattr(cli, 'AgentExecutor', lambda agent: Executor())
    args = Namespace(general=True, workspace_root=str(tmp_path), model=None, base_url=None,
                     timeout=None, provider=None, manifest='manifest.yaml', resume=None,
                     session=None, no_persist=False, no_stream=True, _telemetry_sink=sink)
    if failure == 'prepare':
        with pytest.raises(RuntimeError):
            cli.cmd_chat(args)
    else:
        assert cli.cmd_chat(args) == (1 if failure == 'cancel' else 0)
    events = records(tmp_path / 'telemetry')
    assert events[0]['event'] == 'run.started'
    assert events[-1]['event'] == 'run.finished'
    assert events[-1]['status'] == expected
    assert 'private preparation error' not in json.dumps(events)
