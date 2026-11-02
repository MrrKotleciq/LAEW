"""Google AI Studio's OpenAI-compatible Chat Completions adapter.

Only client function tools are advertised. Gemini thought-signature extensions
are retained verbatim on their owning assistant message/call for continuation.
"""

import copy
import hashlib
import json
import time
from email.utils import parsedate_to_datetime

import requests

from laew.cloud_chat import CloudError, ResponsesTransport, check_cancelled, text_model
from laew.llm.base import LLMProvider, LLMResponse, MessageRole, ToolCall
from laew.llm.cancellation import Cancellation, cancellable_session

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiProvider(LLMProvider):
    native_tools = True
    manages_retries = True
    provider_type = "gemini"
    base_url = API_ROOT

    def __init__(self, credential=None, timeout=120):
        if credential is None:
            from laew.cloud_chat import CloudChatService
            self._credentials = CloudChatService()
            credential = lambda: self._credentials.credential("gemini")[0]
        self.credential = credential
        self.timeout = timeout

    def is_available(self):
        self.credential()
        return True

    def _request(self, session, method, path, token, cancellation, **kwargs):
        for attempt in range(3):
            check_cancelled(cancellation)
            try:
                response = session.request(method, API_ROOT + path,
                    headers={"Authorization": "Bearer " + token}, timeout=(10, self.timeout),
                    allow_redirects=False, stream=True, **kwargs)
            except requests.Timeout:
                check_cancelled(cancellation)
                raise CloudError("TIMEOUT", "Gemini request timed out.") from None
            except requests.RequestException:
                check_cancelled(cancellation)
                raise CloudError("UNAVAILABLE", "Cannot connect to Google AI Studio.") from None
            if response.status_code == 200:
                return response
            status = response.status_code
            retry_after = response.headers.get("Retry-After")
            response.close()
            delay = 0.5 * 2 ** attempt
            if retry_after:
                try:
                    delay = max(0, float(retry_after))
                except ValueError:
                    try:
                        delay = max(0, parsedate_to_datetime(retry_after).timestamp() - time.time())
                    except (ValueError, TypeError, OverflowError):
                        delay = 6
            if status in {429, 500, 502, 503, 504} and attempt < 2 and delay <= 5:
                deadline = time.monotonic() + delay
                while time.monotonic() < deadline:
                    check_cancelled(cancellation)
                    time.sleep(min(.05, max(0, deadline - time.monotonic())))
                continue
            errors = {400: ("INVALID_REQUEST", "Gemini rejected the request. Check model/function-calling support and arguments."),
                      401: ("AUTH_REQUIRED", "Gemini rejected the API key."),
                      403: ("ACCESS_DENIED", "Gemini API key or project access is unavailable."),
                      404: ("MODEL_UNAVAILABLE", "The requested Gemini model is unavailable."),
                      429: ("USAGE_LIMIT", "Gemini resource exhausted. Check project quotas and Retry-After before retrying.")}
            raise CloudError(*errors.get(status, ("SERVER_ERROR", "Google AI Studio returned an unsuccessful response.")))

    def model_catalog(self):
        token = Cancellation()
        with cancellable_session(token) as session:
            response = self._request(session, "GET", "/models", self.credential(), token)
            try:
                body = bytearray()
                for chunk in response.iter_content(16384):
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise ValueError()
                entries = json.loads(body)["data"]
                if not isinstance(entries, list):
                    raise ValueError()
                return [{"id": item["id"].removeprefix("models/"), "label": item["id"].removeprefix("models/"),
                         "tool_calling": "validate_on_use"}
                        for item in entries if text_model(item["id"], "gemini")]
            except (KeyError, TypeError, ValueError):
                raise CloudError("INVALID_RESPONSE", "Gemini returned an invalid model catalog.") from None
            finally:
                response.close()

    def list_models(self):
        return [m["id"] for m in self.model_catalog()]

    def generate(self, messages, model, temperature=0.7, max_tokens=None, stop=None):
        return self.generate_tools(messages, model, [], max_tokens=max_tokens)

    def generate_stream(self, messages, model, temperature=0.7, max_tokens=None, stop=None, cancellation=None):
        yield self.generate_tools(messages, model, [], cancellation=cancellation, max_tokens=max_tokens).content

    def generate_tools(self, messages, model, tools, on_delta=None, cancellation=None, max_tokens=None):
        if not text_model(model, "gemini"):
            raise CloudError("MODEL_UNAVAILABLE", "Choose a Gemini text model with function calling.")
        token = cancellation or Cancellation()
        credential = self.credential()
        scope = "gemini:" + hashlib.sha256(credential.encode()).hexdigest() + ":" + model
        serialized = []
        for message in messages:
            if message.provider_data.get("scope") == scope:
                serialized.append(copy.deepcopy(message.provider_data["message"]))
                continue
            item = {"role": message.role.value, "content": message.content}
            if message.tool_calls:
                item["tool_calls"] = [{"id": call.id, "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments}} for call in message.tool_calls]
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            serialized.append(item)
        payload = {"model": model, "messages": serialized, "stream": True,
                   "stream_options": {"include_usage": True}}
        if tools:
            payload["tools"] = [{"type": "function", "function": {k: v for k, v in tool.items()
                                  if k not in {"type", "strict"}}} for tool in tools]
        if max_tokens:
            payload["max_tokens"] = max_tokens
        chunks, calls, usage = [], {}, {}
        finish = None
        assistant = {"role": "assistant"}
        with cancellable_session(token) as session:
            response = self._request(session, "POST", "/chat/completions", credential, token, json=payload)
            try:
                completed = False
                for frame in ResponsesTransport._frames(response, token):
                    if frame.get("type") == "stream.done":
                        completed = True
                        break
                    if "error" in frame:
                        raise CloudError("STREAM_ERROR", "Gemini reported a stream error.")
                    if frame.get("usage"):
                        usage = {k: frame["usage"].get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
                    for choice in frame.get("choices", []):
                        if choice.get("index", 0) != 0:
                            continue
                        delta = choice.get("delta", {})
                        text = delta.get("content")
                        if text:
                            if not isinstance(text, str):
                                raise ValueError()
                            chunks.append(text)
                            if on_delta:
                                on_delta(text)
                        if "extra_content" in delta:
                            assistant.setdefault("extra_content", {}).update(delta["extra_content"])
                        for part in delta.get("tool_calls") or []:
                            index = part.get("index")
                            if index is None:
                                # Google may send complete calls keyed only by ID,
                                # rather than OpenAI's indexed argument fragments.
                                call_id = part.get("id")
                                if not isinstance(call_id, str) or not call_id:
                                    raise ValueError()
                                index = next((i for i, c in calls.items() if c["id"] == call_id),
                                             max(calls, default=-1) + 1)
                            if not isinstance(index, int) or not 0 <= index < 128:
                                raise ValueError()
                            call = calls.setdefault(index, {"id": "", "type": "function",
                                                          "function": {"name": "", "arguments": ""}})
                            if part.get("id"):
                                if call["id"] and call["id"] != part["id"]:
                                    raise ValueError()
                                call["id"] = part["id"]
                            for key in ("name", "arguments"):
                                fragment = part.get("function", {}).get(key, "")
                                if not isinstance(fragment, str):
                                    raise ValueError()
                                call["function"][key] += fragment
                            if "extra_content" in part:
                                call.setdefault("extra_content", {}).update(part["extra_content"])
                        if choice.get("finish_reason"):
                            finish = choice["finish_reason"]
                check_cancelled(token)
                if not completed or finish not in {"stop", "tool_calls"}:
                    raise CloudError("INCOMPLETE", "Gemini stream ended without a complete response; no tools were executed.")
                ordered = [calls[index] for index in sorted(calls)]
                if any(not c["id"] or not c["function"]["name"] for c in ordered) or len({c["id"] for c in ordered}) != len(ordered):
                    raise ValueError()
                assistant["content"] = "".join(chunks)
                if ordered:
                    assistant["tool_calls"] = ordered
                return LLMResponse(assistant["content"], model, **usage, finish_reason=finish,
                    tool_calls=[ToolCall(c["id"], c["function"]["name"], c["function"]["arguments"]) for c in ordered],
                    provider_data={"scope": scope, "message": assistant})
            except (requests.RequestException, ValueError, TypeError, KeyError):
                check_cancelled(token)
                raise CloudError("STREAM_ERROR", "Gemini returned an invalid or interrupted stream; no tools were executed.") from None
            finally:
                response.close()
