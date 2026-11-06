"""Cover Horizon protocol validation and the private assessment fallback."""

import io
import json
from types import SimpleNamespace

import pytest

from laew.knowledge import horizon
from laew.knowledge.sufficiency import configured_assessor
from laew.llm.llamacpp import LlamaCppProvider
from laew.llm.ollama import OllamaProvider


MEMORIES = [{"content": "I booked the train for Monday."}, {"content": "The ticket is refundable."}]
QUESTION = "What day and time did I book the train for?"
SETTINGS = {"memory_sufficiency": {"enabled": True, "model": "horizon-preferred"}}


@pytest.fixture
def endpoint(monkeypatch):
    state = SimpleNamespace(
        now=100, ready=True, score=0.99, tokens=32, failure=None,
        requests=[], wrong_identity=None,
    )

    class Response(io.BytesIO):
        status = 200

    class Connection:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("127.0.0.1", 8082)
            self.timeout = timeout

        def request(self, method, path, body, headers):
            state.requests.append((method, path, self.timeout, json.loads(body) if body else None))
            self.path = path

        def getresponse(self):
            if state.failure:
                raise state.failure
            identity = {"model_id": horizon.MODEL_ID, "contract": horizon.CONTRACT}
            if state.wrong_identity:
                identity[state.wrong_identity] = "unexpected"
            if self.path == "/readyz":
                data = {**identity, "ready": state.ready, "max_input_tokens": 1024}
            else:
                data = {**identity, "entailment_score": state.score,
                        "not_entailment_score": 1 - state.score, "input_tokens": state.tokens}
            return Response(json.dumps(data).encode())

        def close(self):
            pass

    monkeypatch.setattr(horizon.time, "monotonic", lambda: state.now)
    monkeypatch.setattr(horizon.http.client, "HTTPConnection", Connection)
    monkeypatch.setattr("laew.knowledge.sufficiency.horizon_assessor", horizon.HorizonAssessor())
    return state


def test_readiness_cache_failure_and_recovery(endpoint):
    endpoint.failure = ConnectionRefusedError()
    assessor = horizon.HorizonAssessor()
    assert assessor.assess(QUESTION, MEMORIES)["phase"] == "readiness"
    assert assessor.assess(QUESTION, MEMORIES)["error_category"] == "HorizonCooldown"
    endpoint.now += horizon.RETRY_TTL
    endpoint.failure = None
    assert assessor.assess(QUESTION, MEMORIES)["signal"] == "strong_entailment"
    assert assessor.assess(QUESTION, MEMORIES)["calls"] == 1
    endpoint.failure = TimeoutError()
    result = assessor.assess(QUESTION, MEMORIES)
    assert (result["error_category"], result["phase"]) == ("TimeoutError", "inference")
    assert assessor.assess(QUESTION, MEMORIES)["error_category"] == "HorizonCooldown"
    endpoint.now += horizon.RETRY_TTL
    endpoint.failure = None
    assert assessor.assess(QUESTION, MEMORIES)["status"] == "completed"
    endpoint.now += horizon.READY_TTL
    assert assessor.assess(QUESTION, MEMORIES)["status"] == "completed"
    assert [req[1] for req in endpoint.requests] == [
        "/readyz", "/readyz", "/v1/nli", "/v1/nli", "/v1/nli", "/readyz", "/v1/nli",
        "/readyz", "/v1/nli",
    ]
    assert endpoint.requests[0][:3] == ("GET", "/readyz", 0.25)
    assert endpoint.requests[2] == ("POST", "/v1/nli", 0.8, {
        "premise": "I booked the train for Monday.\n\nThe ticket is refundable.",
        "hypothesis": f"The recalled text directly and completely answers this question: {QUESTION}",
    })


@pytest.mark.parametrize("field", ["model_id", "contract", "readiness"])
def test_wrong_identity_or_readiness_sends_no_memories(endpoint, field):
    if field == "readiness":
        endpoint.ready = False
    else:
        endpoint.wrong_identity = field
    assert horizon.HorizonAssessor().assess(QUESTION, MEMORIES)["status"] == "failed"
    assert len(endpoint.requests) == 1 and endpoint.requests[0][3] is None


def test_wrong_inference_identity_invalidates_cached_readiness(endpoint):
    assessor = horizon.HorizonAssessor()
    assert assessor.assess(QUESTION, MEMORIES)["status"] == "completed"
    endpoint.wrong_identity = "model_id"
    result = assessor.assess(QUESTION, MEMORIES)
    assert result["phase"] == "inference" and result["error_category"] == "HorizonProtocolError"
    endpoint.now += horizon.RETRY_TTL
    assert assessor.assess(QUESTION, MEMORIES)["phase"] == "readiness"
    assert endpoint.requests[-1][3] is None


@pytest.mark.parametrize("score,tokens,signal", [
    (0.95, 32, "strong_entailment"), (0.949, 32, "uncertain"),
    (0.05, 32, "strong_non_entailment"), (0.99, 1024, "possible_truncation"),
])
def test_signals_never_establish_coverage(endpoint, score, tokens, signal):
    endpoint.score, endpoint.tokens = score, tokens
    result = horizon.HorizonAssessor().assess(QUESTION, MEMORIES)
    assert result["signal"] == signal
    assert "sufficient" not in result


@pytest.mark.parametrize("malformed", [float("nan"), 1.1, -0.5, True])
def test_invalid_scores_trip_cooldown(endpoint, malformed):
    endpoint.score = malformed
    assessor = horizon.HorizonAssessor()
    assert assessor.assess(QUESTION, MEMORIES)["error_category"] == "HorizonProtocolError"
    assert assessor.assess(QUESTION, MEMORIES)["error_category"] == "HorizonCooldown"


def test_oversized_input_skips_network(endpoint):
    assert horizon.HorizonAssessor().assess("?", [{"content": "x" * 4001}])["status"] == "abstained"
    assert not endpoint.requests


def test_concurrent_assessment_abstains_without_fallback(endpoint):
    agent = SimpleNamespace()  # Any attempt to select its provider fails the test.
    from laew.knowledge.sufficiency import horizon_assessor
    with horizon_assessor._lock:
        result = configured_assessor(SETTINGS, agent).assess(QUESTION, MEMORIES)
    assert result["signal"] == "busy" and not endpoint.requests


def test_fallback_tracks_active_local_model_and_disables_proxy_and_redirects(endpoint, monkeypatch):
    endpoint.failure = TimeoutError()
    calls = []

    def request(provider, url, payload, *, session):
        assert provider._timeout == 5
        assert not session.trust_env and session.max_redirects == 0
        calls.append((url, payload["model"]))
        return SimpleNamespace(json=lambda: {"choices": [{"message": {"content": '{"sufficient":true}'}}]})

    monkeypatch.setattr(LlamaCppProvider, "_request", request)
    agent = SimpleNamespace(selected_provider=LlamaCppProvider("initial", "http://localhost:8080"),
                            config=SimpleNamespace(model="initial"))
    result = configured_assessor(SETTINGS, agent).assess(QUESTION, MEMORIES)
    assert result["backend"] == "active" and result["signal"] == "reported_sufficient"
    assert "sufficient" not in result
    assert result["horizon"]["phase"] == "readiness"
    agent.selected_provider = LlamaCppProvider("second", "http://[::1]:8085")
    agent.config.model = "second"
    configured_assessor(SETTINGS, agent).assess(QUESTION, MEMORIES)
    assert calls == [("http://127.0.0.1:8080/v1/chat/completions", "initial"),
                     ("http://[::1]:8085/v1/chat/completions", "second")]
    assert len(endpoint.requests) == 1


@pytest.mark.parametrize("provider", [
    object(), OllamaProvider(), LlamaCppProvider("remote", "http://10.0.0.1"),
    LlamaCppProvider("remote", "http://127.0.0.1@example.test"),
])
def test_unknown_cloud_capable_and_nonloopback_providers_are_skipped(endpoint, provider):
    endpoint.failure = TimeoutError()
    agent = SimpleNamespace(selected_provider=provider, config=SimpleNamespace(model="model"))
    result = configured_assessor(SETTINGS, agent).assess(QUESTION, MEMORIES)
    assert result["status"] == "skipped" and result["calls"] == 0
    assert result["error_category"] == "ActiveProviderNotAllowed"
