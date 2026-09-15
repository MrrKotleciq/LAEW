"""Core console commands: system, configuration, provider, prompt, and budget.

Each handler is a pure function ``(args, state) -> int``.  All output goes to
stdout so it can be captured by tests via `capsys`.
"""

from pathlib import Path
from typing import Callable, Dict, Optional

from laew.console.state import SessionState, StateError
from laew.runtime import terminal_allowlist_from_manifest
from laew.prompts.loader import get_prompt_loader
from laew.prompts.context_budget import TokenEstimator


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


# --------------------------------------------------------------------------- #
# check — validate the manifest and workspace configuration (offline)
# --------------------------------------------------------------------------- #
def cmd_check(args: list, state: SessionState) -> int:
    """Validate the system manifest (mirrors ``laew check``)."""
    try:
        manifest = state.load_manifest()
    except StateError as e:
        return _err(e)

    print(f"[OK] Manifest loaded: {state.manifest_path}")
    print(f"  version: {manifest.get('version', 'unknown')}")

    workspace = manifest.get("workspace", {})
    allowed = workspace.get("allowed_paths", [])
    restricted = workspace.get("restricted_paths", [])
    print(f"  workspace root: {workspace.get('root', '.')}")
    print(f"  allowed paths: {len(allowed)}")
    print(f"  restricted paths: {len(restricted)}")

    for rp in restricted:
        full = Path(workspace.get("root", ".")) / rp
        if full.exists():
            print(f"  [!] restricted path exists: {rp}")

    # Report the tool-category contract the console will enforce.
    categories = manifest.get("tools", {}).get("categories", {})
    print(f"  tool categories: {', '.join(categories.keys()) or '(none)'}")
    return 0


# --------------------------------------------------------------------------- #
# info — show resolved runtime configuration (live precedence)
# --------------------------------------------------------------------------- #
def cmd_info(args: list, state: SessionState) -> int:
    """Show the resolved session configuration and precedence chain."""
    try:
        manifest = state.load_manifest()
    except StateError as e:
        return _err(e)

    cfg = state.provider_cfg()
    print(f"manifest: {state.manifest_path}")
    print(f"primary provider: {cfg.get('type')}")
    print(f"provider model: {cfg.get('model', '(unset)')}")
    print(f"provider host: {cfg.get('host', '(unset)')}")
    print(f"provider port: {cfg.get('port', '(unset)')}")
    print(f"provider timeout: {cfg.get('timeout', '(unset)')}")
    print(f"terminal allowlist: {len(state.terminal_allowlist() or [])} commands")

    print("overrides:")
    for key in ("provider", "model", "base-url", "timeout"):
        val = state.overrides.get(key)
        print(f"  {key}: {val if val is not None else '(unset)'}")
    print(f"approval: {state.approval}")
    print(f"trace: {'on' if state.trace else 'off'}")
    return 0


# --------------------------------------------------------------------------- #
# set — session overrides (session > env > manifest > default)
# --------------------------------------------------------------------------- #
def cmd_set(args: list, state: SessionState) -> int:
    """Set a session override: provider|model|base-url|timeout|approval|trace."""
    if len(args) < 2:
        return _err("usage: set <key> <value>  (keys: provider model base-url timeout approval trace)")
    key, value = args[0], args[1]
    try:
        state.set_override(key, value)
    except StateError as e:
        return _err(e)
    print(f"[OK] {key} = {value}")
    return 0


# --------------------------------------------------------------------------- #
# provider — registry dispatch, availability, and one-turn generation
# --------------------------------------------------------------------------- #
def _build_provider(state: SessionState):
    """Build the session provider (session > env > manifest > default)."""
    from laew.runtime import build_provider

    manifest = state.load_manifest()
    return build_provider(
        manifest,
        provider_type=state.overrides.get("provider"),
        base_url=state.overrides.get("base-url"),
        timeout=int(state.overrides["timeout"]) if state.overrides.get("timeout") else None,
    )


def cmd_provider(args: list, state: SessionState) -> int:
    """provider info | models | health | generate "<prompt>"."""
    sub = args[0] if args else "info"
    try:
        provider = _build_provider(state)
        model = state.overrides.get("model") or state.manifest_model()
    except StateError as e:
        return _err(e)

    # info — resolved provider config, no network access (offline-safe).
    if sub == "info":
        from laew.runtime import provider_cfg_from_manifest

        manifest = state.load_manifest()
        cfg = provider_cfg_from_manifest(manifest, state.overrides.get("provider"))
        print(f"provider type: {cfg.get('type')}")
        print(f"model: {cfg.get('model', '(unset)')}")
        print(f"host: {cfg.get('host', '(unset)')}")
        print(f"port: {cfg.get('port', '(unset)')}")
        print(f"timeout: {cfg.get('timeout', '(unset)')}")
        print(f"availability: {provider.is_available()}")
        return 0

    # models — live list from the provider endpoint.
    if sub == "models":
        try:
            installed = provider.list_models()
        except Exception as e:
            return _err(f"could not list models: {e}")
        print(f"{len(installed)} installed model(s):")
        for name in sorted(installed):
            print(f"  - {name}")
        return 0

    # health — availability check.
    if sub == "health":
        try:
            ok = provider.is_available()
        except Exception as e:
            return _err(f"health check failed: {e}")
        print(f"[{'OK' if ok else 'FAIL'}] provider '{provider.__class__.__name__}'"
              f" available: {ok}")
        return 0 if ok else 1

    # generate — one-turn generation proof of the full registry path.
    if sub == "generate":
        if len(args) < 2:
            return _err("usage: provider generate \"<prompt>\"")
        prompt = args[1]
        try:
            response = provider.generate(prompt, model=model or "llama3.1")
        except Exception as e:
            return _err(f"generation failed: {e}")
        print(response.content)
        return 0

    return _err(f"unknown provider subcommand: {sub} (info|models|health|generate)")


# --------------------------------------------------------------------------- #
# prompt — list and show prompt templates (offline)
# --------------------------------------------------------------------------- #
def _prompt_names() -> list:
    """Discover the shipped prompt template names from the repository."""
    prompts_dir = Path(__file__).resolve().parents[3] / "prompts"
    if not prompts_dir.is_dir():
        return []
    return sorted(
        p.stem for p in prompts_dir.glob("*.md") if p.is_file()
    )


def cmd_prompt(args: list, state: SessionState) -> int:
    """prompt list | show <name>."""
    sub = args[0] if args else "list"

    if sub == "list":
        names = _prompt_names()
        print(f"{len(names)} prompt template(s):")
        for name in names:
            print(f"  - {name}")
        return 0

    if sub == "show":
        if len(args) < 2:
            return _err("usage: prompt show <name>")
        name = args[1]
        try:
            prompt = get_prompt_loader().load_prompt(name)
        except FileNotFoundError as e:
            return _err(e)
        print(f"prompt: {prompt.name}")
        print(f"sections: {', '.join(prompt.sections.keys()) or '(none)'}")
        print(f"estimated tokens: {prompt.estimate_tokens()}")
        print(f"within budget: {prompt.is_within_budget()}")
        print("---")
        print(prompt.render())
        return 0

    return _err(f"unknown prompt subcommand: {sub} (list|show)")


# --------------------------------------------------------------------------- #
# budget — estimate tokens for arbitrary text (offline)
# --------------------------------------------------------------------------- #
def cmd_budget(args: list, state: SessionState) -> int:
    """budget "<text>" — estimate token count (~4 chars/token)."""
    if not args:
        return _err('usage: budget "<text>"')
    text = " ".join(args)
    tokens = TokenEstimator.estimate(text)
    print(f"characters: {len(text)}")
    print(f"estimated tokens: {tokens}")
    print(f"rule-of-thumb: {len(text) / max(tokens, 1):.1f} chars/token")
    return 0


# --------------------------------------------------------------------------- #
# tools — list the four registry tools and their operations (offline)
# --------------------------------------------------------------------------- #
def cmd_tools(args: list, state: SessionState) -> int:
    """tools — list tool names and their available operations."""
    from laew.runtime import build_shared_tools
    from laew.agent.executor import AgentExecutor
    from laew.agent.base import Agent, AgentConfig, AgentRole

    # Inspect the operation surface without a live provider: build a dummy
    # agent whose tool set mirrors the shared suite, then reuse the executor's
    # operation-introspection helper to enumerate operations per tool.
    class _StubProvider:
        """Always-reachable provider stand-in for offline introspection."""

        def is_available(self) -> bool:
            return True

    allowlist = state.terminal_allowlist()
    tools = build_shared_tools(allowlist)
    fake = Agent(
        config=AgentConfig(name="probe", model="probe", role=AgentRole.CHIEF),
        provider=_StubProvider(),
        tools=tools,
    )
    executor = AgentExecutor(fake)
    for tool in tools:
        print(f"{tool.name}:")
        print(f"  description: {tool.description}")
        print(f"  operations: {', '.join(executor._valid_operations_for(tool))}")
    return 0


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {
        "check": cmd_check,
        "info": cmd_info,
        "set": cmd_set,
        "provider": cmd_provider,
        "prompt": cmd_prompt,
        "budget": cmd_budget,
        "tools": cmd_tools,
    }