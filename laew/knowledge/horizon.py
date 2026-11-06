"""Loopback Horizon NLI client and advisory Memory coverage signal."""

import http.client
import json
import math
import threading
import time


MODEL_ID = "Horizon-Labs/multilingual-zeroshot-small"
CONTRACT = "horizon-nli-v1"
READY_TIMEOUT = 0.25
INFERENCE_TIMEOUT = 0.8
READY_TTL = 30
RETRY_TTL = 5
SIGNAL_THRESHOLD = 0.95


class HorizonProtocolError(ValueError):
    """The endpoint did not satisfy the Horizon contract."""


def _request(path, timeout, payload=None):
    # Direct HTTP: no redirects, environment proxies or credentials.
    connection = http.client.HTTPConnection("127.0.0.1", 8082, timeout=timeout)
    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
        connection.request("POST" if body else "GET", path, body,
                           {"Content-Type": "application/json"} if body else {})
        response = connection.getresponse()
        if response.status != 200:
            raise HorizonProtocolError(f"Unexpected HTTP status {response.status}")
        body = response.read(4097)
        if len(body) > 4096:
            raise HorizonProtocolError("Response exceeds size limit")
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("model_id") != MODEL_ID or data.get("contract") != CONTRACT:
            raise HorizonProtocolError("Unexpected model or contract")
        return data
    finally:
        connection.close()


def coverage_pair(question, memories):
    """Frame complete answerability as a zero-shot label over recalled text."""
    return {
        "premise": "\n\n".join(m.get("content", "") for m in memories),
        "hypothesis": f"The recalled text directly and completely answers this question: {question}",
    }


def _probability(value):
    return type(value) in (float, int) and 0 <= value <= 1


class HorizonAssessor:
    """Share only readiness state across turns and limit concurrent inference."""

    def __init__(self, *, pair_builder=coverage_pair):
        self._pair_builder = pair_builder
        self._lock = threading.Lock()
        self._ready_until = 0.0
        self._retry_at = 0.0
        self._max_tokens = 0

    def assess(self, question, memories):
        started = time.perf_counter()
        info = {"backend": "horizon", "model": MODEL_ID, "status": "abstained", "calls": 0}
        try:
            if not question.strip() or len(question) > 2000:
                info["signal"] = "input_out_of_bounds"
                return info
            payload = self._pair_builder(question, memories)
            if payload is None:
                info["signal"] = "no_candidate"
            elif not 0 < len(payload["premise"].strip()) <= 4000:
                info["signal"] = "input_out_of_bounds"
            elif self._lock.acquire(blocking=False):
                try:
                    self._assess(payload, info)
                finally:
                    self._lock.release()
            else:
                info["signal"] = "busy"
        finally:
            info["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return info

    def _assess(self, payload, info):
        now = time.monotonic()
        if now < self._retry_at:
            info.update(status="failed", error_category="HorizonCooldown")
            return
        phase = "readiness"
        try:
            if now >= self._ready_until:
                ready = _request("/readyz", READY_TIMEOUT)
                limit = ready.get("max_input_tokens")
                if ready.get("ready") is not True or type(limit) is not int or limit <= 0:
                    raise HorizonProtocolError("Model is not ready")
                self._max_tokens = limit
                self._ready_until = time.monotonic() + READY_TTL

            phase = "inference"
            info["calls"] = 1
            result = _request("/v1/nli", INFERENCE_TIMEOUT, payload)
            entail = result.get("entailment_score")
            non_entail = result.get("not_entailment_score")
            tokens = result.get("input_tokens")
            if (not _probability(entail) or not _probability(non_entail)
                    or not math.isclose(entail + non_entail, 1, abs_tol=1e-5)
                    or type(tokens) is not int or not 0 < tokens <= self._max_tokens):
                raise HorizonProtocolError("Invalid NLI scores or token count")
        except (OSError, http.client.HTTPException, ValueError, RecursionError) as exc:
            self._ready_until = 0.0
            self._retry_at = time.monotonic() + RETRY_TTL
            info.update(status="failed", error_category=type(exc).__name__, phase=phase)
            return

        info["input_tokens"] = tokens
        if tokens == self._max_tokens:
            info["signal"] = "possible_truncation"
            return
        signal = "uncertain"
        if non_entail >= SIGNAL_THRESHOLD:
            signal = "strong_non_entailment"
        elif entail >= SIGNAL_THRESHOLD:
            signal = "strong_entailment"
        info.update(status="completed", signal=signal, entailment_score=entail, not_entailment_score=non_entail)


# CLI and Workbench can construct an assessor for each turn without probing again.
horizon_assessor = HorizonAssessor()
