Step 1 — Automated unit tests (fastest signal)

  Run the CLI test suite from the project root:

  python -m pytest tests/unit/test_cli.py -v

  Expected: all 19 tests pass, including the three TestChatCommand cases:
  - test_chat_runs_and_exits — mocks the executor, feeds hello + exit, expects exit code 0 and output "Agent: Hello from
    the agent".
  - test_chat_missing_manifest — expects a clean [FAIL] Could not load manifest and exit code 1.
  - test_chat_no_llm_available — simulates an unreachable Ollama, expects [FAIL] Could not connect to a local LLM and
    exit code 1.

  ▎ These don't need Ollama — the LLM is mocked. They prove the CLI wiring and chat-loop logic are sound.

  If any fail here, the manual test in Step 3 won't pass — stop and report the traceback.

  ---

  Step 2 — Verify the command is registered

  python laew/cli.py --help

  Expect to see chat listed among the subcommands. Then:

  python laew/cli.py chat --help

  Expect the flags:

  --model MODEL          Ollama model name (overrides the manifest model role)
  --base-url BASE_URL    Ollama API base URL (default: http://localhost:11434)
  --manifest MANIFEST    Path to system manifest (default: manifests/SYSTEM_MANIFEST.yaml)

  ---

  Step 3 — Live end-to-end test (requires Ollama)

  3a. Confirm Ollama is up

  curl http://localhost:11434/api/tags
  Expect a JSON object with a "models" array (may be empty if you haven't pulled anything yet).

  3b. Start the chat

  python laew/cli.py chat

  Expected startup output:
  Starting chat with llama3.1 (Ollama at http://localhost:11434)
  Type 'exit' or 'quit' to end the session.
  ------------------------------------------------------------
  You:

  Step 4 — Drive a conversation

  At the You: prompt, try each check:

  ┌─────┬──────────────────────────────────┬────────────────────────────────────────────────────────────────────────┐
  │  #  │              Input               │                            What to look for                            │
  ├─────┼──────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ 1   │ hello                            │ Agent replies (a short greeting from llama3.1).                        │
  ├─────┼──────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ 2   │ What is 2+2?                     │ A reasoned answer.                                                     │
  ├─────┼──────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤
  │     │ List the files in this directory │ The agent emits a tool_call JSON block; you should see it execute and  │
  │ 3   │  using the filesystem tool.      │ then give a result-based answer. This exercises the filesystem tool    │
  │     │                                  │ path.                                                                  │
  ├─────┼──────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ 4   │ exit                             │ Prints Session ended. and returns to your shell prompt. Clean exit     │
  │     │                                  │ code 0.                                                                │
  └─────┴──────────────────────────────────┴────────────────────────────────────────────────────────────────────────┘

  Multi-turn check

  Ask a follow-up question that references a prior turn, e.g. first My favorite color is blue, then What is my favorite
  color?. A correct reply (blue) confirms conversation history persists across turns.

  Tool-call introspection (advanced)

  Ask something tool-requiring and watch the JSON block formatting. You'll see the executor loop turn the LLM's
  ```tool_call {…} ``` block into an actual tool invocation. Use git status-type prompts to exercise the git tool, or
  read the file docs/ROADMAP.md for filesystem.

  ---

  Step 5 — Exit & error-path checks

  | 5a | Connectivity failure | Stop Ollama (quit the app), then python laew/cli.py chat. Expect [FAIL] Could not
  connect to a local LLM: No LLM providers are available and exit code 1 — no traceback. |
  | 5b | Missing manifest | python laew/cli.py chat --manifest nonexistent.yaml — expect [FAIL] Could not load manifest
  and exit code 1. |
  | 5c | Ctrl+C | While the agent is generating, press Ctrl+C — expect Session interrupted. and a clean return. |
  | 5d | Model override | python laew/cli.py chat --model mistral:latest — the startup line should show mistral:latest.
  |

  ---

  Step 6 — Confirm exit codes programmatically

  printf 'hello\nexit\n' | python laew/cli.py chat; echo "exit code: $?"
  Expect exit code 0 at the end (if Ollama is running — replace the prompt inputs as needed).

  ---

  Quick troubleshooting

  ┌───────────────────────────────────┬───────────────────────────┬────────────────────────────────────────────────┐
  │              Symptom              │       Likely cause        │                      Fix                       │
  ├───────────────────────────────────┼───────────────────────────┼────────────────────────────────────────────────┤
  │ [FAIL] Could not connect to a     │ Ollama not running, or    │ Start Ollama; check --base-url.                │
  │ local LLM                         │ wrong port                │                                                │
  ├───────────────────────────────────┼───────────────────────────┼────────────────────────────────────────────────┤
  │ Error: Tool 'filesystem' not      │ Model didn't format the   │ ollama pull a stronger model (e.g. llama3.1 8B │
  │ found. style output in Step 4 #3  │ tool-call block correctly │  or qwen2.5); the executor only parses the     │
  │                                   │                           │ exact tool_call JSON block.                    │
  ├───────────────────────────────────┼───────────────────────────┼────────────────────────────────────────────────┤
  │ ModuleNotFoundError: requests     │ Missing dependency        │ pip install requests.                          │
  ├───────────────────────────────────┼───────────────────────────┼────────────────────────────────────────────────┤
  │                                   │                           │ The executor stops at the configured cap and   │
  │ Agent loops forever on tool calls │ max_iterations reached    │ returns an error rather than hanging — a       │
  │                                   │                           │ graceful, not silent, stop.                    │
  └───────────────────────────────────┴───────────────────────────┴────────────────────────────────────────────────┘

  ---

  The single most valuable test is Step 4 #3 + the multi-turn check — they prove the two things that matter: tools
  actually execute from inside the chat loop, a