"""Chief receives actual WebTool results and infrastructure failures."""

import json
from unittest.mock import patch

import requests

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.llm.base import LLMResponse
from laew.tools.web import WebTool


class Provider:
    def __init__(self):
        self.calls = 0
        self.observation = ""

    def is_available(self):
        return True

    def generate(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            call = {"tool": "WebTool", "operation": "search_web", "args": {"query": "test"}}
            return LLMResponse(content="```tool_call\n" + json.dumps(call) + "\n```", model="fixture")
        self.observation = messages[-1].content
        return LLMResponse(content="Finished.", model="fixture")


class Response:
    status_code = 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, size):
        yield b'{"results": [{"title": "Fixture", "url": "https://example.org"}]}'


def test_chief_observes_search_results_and_unavailability():
    for outcome, expected, success in ((Response(), "https://example.org", True),
                                       (requests.ConnectionError(), "unavailable", False)):
        provider = Provider()
        executor = AgentExecutor(Agent(AgentConfig(), provider=provider, tools=[WebTool()]))
        with patch("requests.get", side_effect=outcome if isinstance(outcome, Exception) else None,
                   return_value=outcome):
            result = executor.run("Search the web")
        assert result.steps[0].tool_result.success is success
        assert expected in provider.observation
