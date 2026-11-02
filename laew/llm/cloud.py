"""OpenAI Responses adapter for the shared Chief Agent execution loop."""

import copy
import hashlib

from laew.cloud_chat import CloudError, ResponsesTransport, check_cancelled
from laew.llm.base import LLMMessage, LLMProvider, LLMResponse, MessageRole, ToolCall
from laew.llm.cancellation import Cancellation


class OpenAIProvider(LLMProvider):
    native_tools = True
    manages_retries = True
    base_url = "https://api.openai.com/v1"

    def __init__(self, provider_type="openai-api", credential=None, transport=None,
                 account_id=None, timeout=120):
        self.provider_type = provider_type
        if credential is None:
            from laew.cloud_chat import CloudChatService
            self._credentials = CloudChatService()
            credential = lambda: self._credentials.credential(provider_type, account_id)[0]
        self.credential = credential
        self.transport = transport or ResponsesTransport()
        self.transport.timeout = timeout
        self.account_id = account_id

    def is_available(self):
        # Credential checks are local; an actual inference/catalog request reports connectivity.
        self.credential()
        return True

    def list_models(self):
        return [m["id"] for m in self.transport.models(self.credential(), self.provider_type)]

    def generate(self, messages, model, temperature=0.7, max_tokens=None, stop=None):
        return self.generate_tools(messages, model, [])

    def generate_stream(self, messages, model, temperature=0.7, max_tokens=None, stop=None,
                        cancellation=None):
        # The executor uses generate_tools for native streaming and receives structured output.
        response = self.generate_tools(messages, model, [], cancellation=cancellation)
        yield response.content

    def generate_tools(self, messages, model, tools, on_delta=None, cancellation=None):
        credential = self.credential()
        scope = self.provider_type + ":" + str(self.account_id or hashlib.sha256(credential.encode()).hexdigest()) + ":" + model
        instructions, inputs = [], []
        for message in messages:
            if message.role == MessageRole.SYSTEM:
                instructions.append(message.content)
            elif message.role == MessageRole.TOOL:
                inputs.append({"type": "function_call_output", "call_id": message.tool_call_id,
                               "output": message.content})
            elif message.provider_data.get("scope") == scope:
                inputs.extend(copy.deepcopy(message.provider_data["output"]))
            else:
                if message.content:
                    inputs.append({"role": message.role.value, "content": message.content})
                for call in message.tool_calls:
                    item = {"type": "function_call", "call_id": call.id,
                            "name": call.name, "arguments": call.arguments}
                    if self.provider_type == "chatgpt":
                        item["namespace"] = "laew"
                    inputs.append(item)
        chunks, output, usage = [], [], {}
        for event in self.transport.stream(credential, self.provider_type, model, inputs,
                cancellation or Cancellation(), tools=tools, instructions="\n\n".join(instructions)):
            check_cancelled(cancellation)
            if event["type"] == "delta":
                chunks.append(event["text"])
                if on_delta:
                    on_delta(event["text"])
            elif event["type"] == "response":
                output = event["output"]
            elif event["type"] == "usage":
                usage = event["usage"]
        calls = []
        check_cancelled(cancellation)
        for item in output:
            if item.get("type") == "function_call":
                if (not all(isinstance(item.get(k), str) and item[k] for k in ("call_id", "name"))
                        or not isinstance(item.get("arguments"), str)
                        or item.get("namespace") not in (None, "laew")):
                    raise CloudError("INVALID_RESPONSE", "Invalid OpenAI function call; nothing was executed.")
                calls.append(ToolCall(item["call_id"], item["name"], item["arguments"]))
        if len({c.id for c in calls}) != len(calls):
            raise CloudError("INVALID_RESPONSE", "Duplicate call IDs in one response.")
        if not chunks:
            text = "".join(part.get("text", part.get("refusal", "")) for item in output
                           if item.get("type") == "message" for part in item.get("content", [])
                           if part.get("type") in {"output_text", "refusal"})
            if text:
                chunks.append(text)
                if on_delta:
                    on_delta(text)
        if not chunks and not calls:
            raise CloudError("EMPTY_RESPONSE", "OpenAI completed without text or a function call.")
        return LLMResponse("".join(chunks), model, **usage, finish_reason="tool_calls" if calls else "stop",
                           tool_calls=calls, provider_data={"scope": scope, "output": output})
