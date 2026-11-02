"""Cloud credentials and bounded HTTP transport. Tool execution belongs to LAEW."""

import hashlib
import json
import os
import threading
import time

import requests

from laew.llm.cancellation import Cancellation, cancellable_session
from laew.llm.base import LLMError

CLOUD_PROVIDERS = {"openai-api", "chatgpt", "gemini"}
API_ROOT = "https://api.openai.com/v1"
INSTRUCTIONS = "You are a helpful text assistant. Reply in the user's language. You have no tools or access to local files."


def text_model(model, provider):
    """Conservative catalog filter; inference still validates account capabilities."""
    model = model.lower().removeprefix("models/")
    excluded = ("audio", "tts", "image", "embedding", "realtime", "live", "transcrib", "omni", "banana", "robot")
    if any(part in model for part in excluded):
        return False
    return model.startswith("gemini-") if provider == "gemini" else model.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-"))


class CloudError(LLMError):
    def __init__(self, code, message):
        super().__init__(message, code)


def check_cancelled(token):
    if token and token.is_set():
        from laew.agent.executor import StreamCancelled
        raise StreamCancelled()


class ResponsesTransport:
    """Only the official OpenAI origin is used; local provider settings are ignored."""

    def _response(self, session, method, path, credential, **kwargs):
        try:
            response = session.request(method, API_ROOT + path,
                headers={"Authorization": "Bearer " + credential},
                timeout=(10, getattr(self, "timeout", 120)), allow_redirects=False, **kwargs)
        except requests.Timeout:
            raise CloudError("TIMEOUT", "OpenAI request timed out.") from None
        except requests.RequestException:
            raise CloudError("UNAVAILABLE", "Cannot connect to OpenAI.") from None
        if response.status_code != 200:
            code = response.status_code
            response.close()
            errors = {401: ("AUTH_REQUIRED", "OpenAI rejected the credential. Check the API key or sign in again."),
                      403: ("ACCESS_DENIED", "This account cannot access the requested OpenAI resource."),
                      404: ("MODEL_UNAVAILABLE", "The requested OpenAI model is unavailable."),
                      429: ("USAGE_LIMIT", "OpenAI usage or rate limit reached. Check account limits and credits."),
                      400: ("INVALID_REQUEST", "OpenAI rejected the request. Check that the exact model supports text Responses.")}
            error = errors.get(code, ("SERVER_ERROR", "OpenAI returned an unsuccessful HTTP response."))
            raise CloudError(*error)
        return response

    def models(self, credential, provider):
        if provider == "gemini":
            from laew.llm.gemini import GeminiProvider
            return GeminiProvider(credential=lambda: credential).model_catalog()
        with requests.Session() as session:
            response = self._response(session, "GET", "/models", credential, stream=True)
            try:
                body = bytearray()
                for chunk in response.iter_content(16384):
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise ValueError()
                data = json.loads(body)
                if not isinstance(data, dict): raise ValueError()
                entries = data.get('models' if provider == 'chatgpt' else 'data')
                if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries): raise ValueError()
                if provider == "chatgpt":
                    results = [{"id": item["slug"], "label": item.get("display_name", item["slug"])}
                               for item in entries if item.get("visibility") == "list"]
                else:
                    results = [{"id": item["id"], "label": item["id"]} for item in entries
                               if text_model(item.get("id", ""), "openai-api")]
                if not all(isinstance(item['id'], str) and isinstance(item['label'], str) for item in results): raise ValueError()
                return results
            except (ValueError, KeyError, TypeError):
                raise CloudError("INVALID_RESPONSE", "OpenAI returned an invalid model catalog.") from None
            finally:
                response.close()

    @staticmethod
    def _frames(response, cancellation):
        pending = bytearray()
        data_lines = []
        size = 0
        deadline = time.monotonic() + 300
        for chunk in response.iter_content(chunk_size=256):
            check_cancelled(cancellation)
            size += len(chunk)
            if size > 4 * 1024 * 1024:
                raise CloudError("RESPONSE_LIMIT", "OpenAI response exceeded the size limit.")
            if time.monotonic() > deadline:
                raise CloudError("TIMEOUT", "OpenAI response exceeded five minutes.")
            pending.extend(chunk)
            while b'\n' in pending:
                raw, _, rest = pending.partition(b'\n'); pending = bytearray(rest)
                line = raw.rstrip(b'\r').decode('utf-8')
                if line.startswith('data:'): data_lines.append(line[5:].lstrip())
                if not line and data_lines:
                    raw_frame = '\n'.join(data_lines); data_lines = []
                    if raw_frame == '[DONE]':
                        yield {"type": "stream.done"}
                        continue
                    frame = json.loads(raw_frame)
                    if not isinstance(frame, dict): raise ValueError()
                    yield frame

    def stream(self, credential, provider, model, messages, cancellation, *, tools=None, instructions=None):
        payload = {"model": model, "instructions": instructions or INSTRUCTIONS, "input": messages,
                   "stream": True, "store": False}
        if tools is not None:
            payload["include"] = ["reasoning.encrypted_content"]
            payload["tools"] = ([{"type": "namespace", "name": "laew",
                                 "description": "Tools executed by the LAEW workspace with permission checks.",
                                 "tools": tools}] if provider == "chatgpt" and tools else tools)
        if provider == "openai-api":
            try:
                limit = int(os.environ.get("LAEW_OPENAI_MAX_OUTPUT_TOKENS", "4096"))
                if not 1 <= limit <= 131072: raise ValueError()
            except ValueError:
                raise CloudError("CONFIGURATION", "LAEW_OPENAI_MAX_OUTPUT_TOKENS must be between 1 and 131072.") from None
            payload["max_output_tokens"] = limit
        check_cancelled(cancellation)
        with cancellable_session(cancellation) as session:
            response = None
            try:
                response = self._response(session, "POST", "/responses", credential, json=payload, stream=True)
                completed = False
                finished_items = {}
                pending_items = set()
                for frame in self._frames(response, cancellation):
                    check_cancelled(cancellation)
                    kind = frame.get("type")
                    if kind in {"response.output_text.delta", "response.refusal.delta"}:
                        delta = frame.get("delta")
                        if not isinstance(delta, str): raise ValueError()
                        yield {"type": "delta", "text": delta}
                    elif kind in {"response.output_item.added", "response.output_item.done"}:
                        index, item = frame.get("output_index"), frame.get("item")
                        if not isinstance(index, int) or index < 0 or not isinstance(item, dict):
                            raise ValueError()
                        if kind.endswith("added"):
                            pending_items.add(index)
                        else:
                            finished_items[index] = item
                            pending_items.discard(index)
                    elif kind == "response.completed":
                        result = frame.get("response", {})
                        if not isinstance(result, dict): raise ValueError()
                        if result.get("status") != "completed": raise ValueError()
                        # This route never requests tools. Unexpected tool output is not executable.
                        # SIWC can omit output from the terminal event. Only
                        # completed items are replayable; never use argument deltas.
                        output = result.get("output") or [finished_items[i] for i in sorted(finished_items)]
                        if pending_items:
                            raise CloudError("INCOMPLETE", "OpenAI completed with unfinished output items.")
                        if not isinstance(output, list) or not all(isinstance(item, dict) for item in output): raise ValueError()
                        allowed = {"message", "reasoning", "function_call"} if tools is not None else {"message", "reasoning"}
                        if any(item.get("type") not in allowed for item in output):
                            raise CloudError("UNEXPECTED_TOOL", "OpenAI returned an unexpected tool request; nothing was executed.")
                        usage = result.get("usage") or {}
                        if not isinstance(usage, dict): raise ValueError()
                        check_cancelled(cancellation)
                        if tools is not None:
                            yield {"type": "response", "output": output}
                        yield {"type": "usage", "usage": {"prompt_tokens": usage.get("input_tokens"),
                               "completion_tokens": usage.get("output_tokens"), "total_tokens": usage.get("total_tokens")}}
                        completed = True
                        break
                    elif kind in {"response.failed", "response.incomplete", "error"}:
                        raise CloudError("INCOMPLETE", "OpenAI did not complete the response. The partial answer is incomplete.")
                check_cancelled(cancellation)
                if not completed:
                    raise CloudError("INCOMPLETE", "OpenAI stream ended before completion.")
            except (requests.RequestException, ValueError, UnicodeError):
                check_cancelled(cancellation)
                raise CloudError("STREAM_ERROR", "OpenAI returned an invalid or interrupted stream.") from None
            except CloudError:
                check_cancelled(cancellation)
                raise
            finally:
                if response is not None: response.close()


class CloudChatService:
    """Credential/catalog facade shared by Workbench and provider builders."""

    def __init__(self, auth=None, transport=None):
        if auth is None:
            from laew.chatgpt_auth import ChatGPTAuth
            auth = ChatGPTAuth()
        self.auth = auth
        self.transport = transport or ResponsesTransport()
        self._lock = threading.RLock()

    def credential(self, provider, account_id=None):
        if provider in {"openai-api", "gemini"}:
            variable = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
            key = os.environ.get(variable, "").strip()
            if not key:
                raise CloudError("AUTH_REQUIRED", f"Set {variable} in the LAEW backend environment.")
            return key, hashlib.sha256(key.encode()).hexdigest()
        if provider == "chatgpt":
            if not account_id:
                accounts = [a for a in self.auth.status().get("accounts", []) if a["authenticated"]]
                if len(accounts) == 1:
                    account_id = accounts[0]["id"]
            return self.auth.credential(account_id), account_id
        raise CloudError("INVALID_PROVIDER", "Choose OpenAI API or ChatGPT.")

    def status(self, session_id=None):
        return {"api_key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
                "gemini_api_key_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
                **self.auth.status(session_id)}

    def provider(self, provider, account_id=None, timeout=120):
        from laew.llm.cloud import OpenAIProvider
        from laew.llm.gemini import GeminiProvider
        # Resolve at request time so token rotation/disconnection takes effect.
        credential = lambda: self.credential(provider, account_id)[0]
        if provider == "gemini":
            return GeminiProvider(credential=credential, timeout=timeout)
        return OpenAIProvider(provider, credential=credential, transport=self.transport,
                              account_id=account_id, timeout=timeout)

    def logout(self, account_id):
        return self.auth.logout(account_id)

    def close(self):
        self.auth.close()
