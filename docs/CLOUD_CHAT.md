---
type: docs
title: Unified model providers
scope: Chief Agent model adapters, authentication and tool calling
read_when:
  - configuring cloud models
  - troubleshooting function calling
---
# Unified model providers

All providers use AgentExecutor, the active tool registry, PermissionBroker and the same project RAG. Providers serialize inference only; they never execute tools. The former separate text-only cloud conversation has been removed.

## General Chat

Choose **General Chat** in the Workbench project list to use the Chief Agent without an active project. The context panel shows the global vault and sources used in the current run. Switching scope preserves the selected provider and model. Saved conversations can be reopened after a backend restart.

General Chat exposes global RAG, WebTool and the filesystem operations constrained to `@knowledge`. Project and hybrid RAG, project aliases, Git and terminal are unavailable. Global note writes use the existing explicit approval and note validation. General scope requires separate Projects and Knowledge roots and does not create a project collection.

In the CLI use `laew chat --general`, optionally with `--workspace-root` pointing to a directory containing `Projects` and `Knowledge`. Add `--new-conversation` to persist it, or use `--conversation ID` to resume. A noninteractive console cannot approve a global write.

## Configuration

Select Manifest default, llama.cpp, OpenAI API key, ChatGPT OAuth or Google AI Studio in Workbench. Load models or enter an exact model ID. API keys are read from backend environment variables OPENAI_API_KEY and GEMINI_API_KEY. Models & Services can save them to Windows user environment variables and apply them immediately to the current backend. When setting them outside the UI, restart the backend from an updated environment; never put secrets in chat, manifests or knowledge. OAuth retains the existing protected OS keyring, refresh, registration and logout flow. Install optional authentication dependencies with `pip install ".[cloud]"`.

CLI: `laew chat --provider gemini --model gemini-3.8-flash` (or openai-api/chatgpt with an exact available model). Console provider/model overrides use the same registry. Cloud adapters ignore local endpoint overrides and do not select a different model automatically.

## Protocols

Local models retain the explicit fenced tool_call protocol. Ordinary JSON fences are not executable. OpenAI API uses official Responses function tools. OAuth uses namespaces, store:false, stream:true, explicit input history and no unsupported sampling/token fields. Complete output_item.done events are collected because OAuth response.completed can omit output. Execution waits for completed inference.

Gemini uses https://generativelanguage.googleapis.com/v1beta/openai/chat/completions with the existing requests library, not Responses. Streamed arguments are assembled by call index, or by call ID when Google sends complete function calls without an index; call IDs and extra_content thought signatures survive continuation. No Google SDK dependency is needed. Catalog filtering excludes known audio, image, embedding and live models; inference remains the authority on account/model support.

Schemas derive from registered operation metadata and Python signatures. The executor validates arguments, calls the shared permission callback, records the actual result and returns it with the originating call ID. Invalid arguments, denial and tool failures become results. Duplicate call IDs and identical mutating operations within a run do not execute twice. Limits bound iterations, call count and elapsed checks. Synchronous tool execution still depends on individual wrapper timeout support; it is not forcibly terminated in a background thread.

## History and streaming

Workbench and CLI store new conversations through the shared SessionStore; legacy named CLI sessions retain their existing user/final-answer format. Switching models preserves the conversation. Native tool messages are provider-neutral with optional scoped continuation metadata. Local adapters receive text renderings of completed native history. See [conversation history](architecture/CONVERSATION_HISTORY.md) for persistence and recovery.

The existing Sources, approval and Stop interfaces serve every provider. Cloud selection sends conversation context and requested tool results to that provider. It does not upload the entire vault or create hosted vector stores. Session approvals include all arguments. Cancellation closes the transport; incomplete function calls never execute.

## Errors and quotas

Missing credentials, rejected authentication, unavailable models, invalid requests, timeouts and incomplete streams fail explicitly. No provider or billing fallback occurs. Gemini retries only transient HTTP status responses before consuming the stream, up to three attempts, honoring Retry-After up to five seconds; larger delays are returned for user retry. Streams and tool mutations are not automatically retried. OpenAI API output limit defaults to 4096 via LAEW_OPENAI_MAX_OUTPUT_TOKENS; OAuth omits this field.

Google Free Tier depends on the project and model, not its name. The catalog does not prove free eligibility. gemini-3.8-flash and gemini-3.5-flash-lite are documented text models; actual availability is obtained from the API. Grounding and other separately billed hosted tools are never enabled.

## Validation

Run `python -m pytest tests/unit tests/integration`, `node --check laew/ui/app.js`, and `node --test tests/ui/*.test.js`. Offline tests block external/production service connections and production scheduler startup. Use a fresh --basetemp and TEMP/TMP directory where Windows sandbox cleanup requires it.

Opt-in live validation: `python scripts/validate_cloud_integration.py --provider chatgpt --model <available-model>` with repository PYTHONPATH. It creates disposable project/knowledge roots, deterministic embeddings and an in-memory vector store, and checks text, real RagTool retrieval and real file reading. --serve exposes an isolated Workbench for approval testing. No scheduler starts. Mocks are not evidence of real API access.

Manual UI verification: choose each provider, inspect credential status, load models, send a short request, then request a file read and RagTool retrieval. Inspect Sources. In Manual mode request a disposable file write, deny it and verify no file, then repeat and allow once. Change model and verify transcript/project preservation. Stop an active request and verify no pending call executes afterward.

References: [OpenAI OAuth restrictions](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations), [inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai), [pricing](https://ai.google.dev/gemini-api/docs/pricing), [limits](https://ai.google.dev/gemini-api/docs/rate-limits).
