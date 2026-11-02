"""Bounded search parsing and error propagation without external services."""

import json
from unittest.mock import patch

import pytest
import requests

from laew.tools.web import WebTool


class Response:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))
    def iter_content(self, size): yield self.body


def test_parses_bounded_results_and_preserves_real_dates():
    body = json.dumps({"results": [{"title": "Title", "url": "https://example.org", "content": "Text", "engine": "example"}]}).encode()
    with patch("requests.get", return_value=Response(200, body)) as get:
        result = WebTool().search_web("test", domain="example.org")
    assert result.success and result.data["results"][0]["title"] == "Title"
    assert "published_date" not in result.data["results"][0]
    assert get.call_args.kwargs["params"]["q"] == "test site:example.org"


@pytest.mark.parametrize("response, expected", [
    (Response(403, b""), "403"),
    (Response(200, b"<html>"), "invalid JSON"),
    (Response(200, b'{"results": [], "unresponsive_engines": [["engine", "timeout"]]}'), "engine failures"),
    (Response(200, b"x" * (1024 * 1024 + 1)), "exceeded"),
])
def test_errors_are_not_reported_as_empty_results(response, expected):
    with patch("requests.get", return_value=response):
        result = WebTool().search_web("test")
    assert not result.success and expected in result.error_message


def test_empty_results_are_distinct():
    with patch("requests.get", return_value=Response(200, b'{"results": []}')):
        result = WebTool().search_web("test")
    assert result.success and result.data["results"] == []


@pytest.mark.parametrize("exception, expected", [
    (requests.Timeout(), "timed out"), (requests.ConnectionError(), "unavailable"),
])
def test_network_failures(exception, expected):
    with patch("requests.get", side_effect=exception):
        result = WebTool().search_web("test")
    assert not result.success and expected in result.error_message
