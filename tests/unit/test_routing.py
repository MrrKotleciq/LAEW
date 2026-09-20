"""Unit tests for role-based provider dispatch and fallback behavior (Milestone 15).

Tests the MANIFEST-DRIVEN ROUTING system where:
- Roles (primary, embedding, reviewer) map to ordered provider name lists
- Ordered fallback chain tries providers sequentially on failure
- Typed errors: NO_PROVIDER_FOR_ROLE, PROVIDER_NOT_FOUND, ALL_PROVIDERS_FAILED
- Zero-configuration routing controlled entirely via SYSTEM_MANIFEST.yaml

Importers: laew.runtime.build_provider_for_role, laew.llm.registry.get_provider_for_role
Affected API: build_provider_for_role(), get_provider_for_role()
Data schemas: manifest.agent.llm.roles mapping, manifest.agent.llm.providers list
User verbatim instruction: "Create comprehensive routing tests in `tests/unit/test_routing.py` to validate role-based dispatch and fallback behavior"
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from laew.llm import LLMError
from laew.llm.registry import ProviderRegistry, build_ollama
from laew.runtime import build_provider_for_role


# --------------------------------------------------------------------------- #
# Test provider builders
# --------------------------------------------------------------------------- #

def build_success_provider(name: str):
    """Builder that returns a successful provider."""
    def _builder(cfg, *, base_url=None, timeout=None):
        provider = build_ollama(cfg, base_url=base_url, timeout=timeout)
        provider._name = name or cfg.get("name", "unknown")  # For identification
        return provider
    return _builder


def build_failing_provider(name: str, error_msg: str = "Connection failed"):
    """Builder that always fails with the given error."""
    def _builder(cfg, *, base_url=None, timeout=None):
        # Only fail if this builder matches the expected provider name
        if name is None or cfg.get("name") == name:
            raise LLMError(error_msg, code="CONNECTION_FAILED")
        # Otherwise succeed (allows conditional failing)
        provider = build_ollama(cfg, base_url=base_url, timeout=timeout)
        provider._name = cfg.get("name", "unknown")
        return provider
    return _builder


# --------------------------------------------------------------------------- #
# Role-based provider selection tests
# --------------------------------------------------------------------------- #

def test_get_provider_for_role_success_primary():
    """Role dispatch returns first provider when it builds successfully."""
    registry = ProviderRegistry()
    registry.register("ollama", build_success_provider("primary-ok"))

    manifest = {
        "agent": {
            "llm": {
                "providers": [
                    {"name": "primary-ok", "type": "ollama"},
                    {"name": "secondary-ok", "type": "ollama"},
                ],
                "roles": {
                    "primary": ["primary-ok", "secondary-ok"],
                }
            }
        }
    }

    provider = build_provider_for_role(manifest, "primary", _registry=registry)
    assert provider._name == "primary-ok"


def test_get_provider_for_role_fallback_to_secondary():
    """Role dispatch falls back to secondary provider when primary fails."""
    registry = ProviderRegistry()
    registry.register("ollama", build_success_provider("secondary-ok"))
    registry.register("ollama", build_failing_provider("primary-fail"))

    manifest = {
        "agent": {
            "llm": {
                "providers": [
                    {"name": "primary-fail", "type": "ollama"},
                    {"name": "secondary-ok", "type": "ollama"},
                ],
                "roles": {
                    "primary": ["primary-fail", "secondary-ok"],
                }
            }
        }
    }

    provider = build_provider_for_role(manifest, "primary", _registry=registry)
    assert provider._name == "secondary-ok"


def test_get_provider_for_role_all_fail_chained_error():
    """Role dispatch raises ALL_PROVIDERS_FAILED when all providers fail."""
    registry = ProviderRegistry()
    # Use different provider types so both builders are registered
    registry.register("ollama-fail1", build_failing_provider("fail1", "Error 1"))
    registry.register("ollama-fail2", build_failing_provider("fail2", "Error 2"))

    manifest = {
        "agent": {
            "llm": {
                "providers": [
                    {"name": "fail1", "type": "ollama-fail1"},
                    {"name": "fail2", "type": "ollama-fail2"},
                ],
                "roles": {
                    "primary": ["fail1", "fail2"],
                }
            }
        }
    }

    with pytest.raises(LLMError) as excinfo:
        build_provider_for_role(manifest, "primary", _registry=registry)

    assert excinfo.value.code == "ALL_PROVIDERS_FAILED"
    assert "Failed to build any provider for role 'primary'" in excinfo.value.message
    assert "CONNECTION_FAILED: Error 2" in excinfo.value.message  # Last error in chain


def test_get_provider_for_role_no_role_manifest():
    """Role dispatch raises NO_PROVIDER_FOR_ROLE when role missing from manifest."""
    registry = ProviderRegistry()
    registry.register("ollama", build_success_provider("any"))

    manifest = {
        "agent": {
            "llm": {
                "providers": [{"name": "any", "type": "ollama"}],
                "roles": {
                    "embedding": ["any"],  # 'primary' role missing
                }
            }
        }
    }

    with pytest.raises(LLMError) as excinfo:
        build_provider_for_role(manifest, "primary", _registry=registry)

    assert excinfo.value.code == "NO_PROVIDER_FOR_ROLE"
    assert "No provider list found for role 'primary'" in excinfo.value.message


def test_get_provider_for_role_provider_not_found_soft_skip():
    """Role dispatch skips missing provider names and tries next in list."""
    registry = ProviderRegistry()
    registry.register("ollama", build_success_provider("secondary-ok"))

    manifest = {
        "agent": {
            "llm": {
                "providers": [
                    {"name": "secondary-ok", "type": "ollama"},
                    # Note: "missing-provider" is not in providers list
                ],
                "roles": {
                    "primary": ["missing-provider", "secondary-ok"],
                }
            }
        }
    }

    provider = build_provider_for_role(manifest, "primary", _registry=registry)
    assert provider._name == "secondary-ok"


def test_get_provider_for_role_empty_provider_list():
    """Role dispatch raises NO_PROVIDER_FOR_ROLE when role has empty provider list."""
    registry = ProviderRegistry()

    manifest = {
        "agent": {
            "llm": {
                "providers": [],
                "roles": {
                    "primary": [],  # Empty list
                }
            }
        }
    }

    with pytest.raises(LLMError) as excinfo:
        build_provider_for_role(manifest, "primary", _registry=registry)

    assert excinfo.value.code == "NO_PROVIDER_FOR_ROLE"
    assert "No provider list found for role 'primary'" in excinfo.value.message


def test_get_provider_for_role_none_provider_list():
    """Role dispatch raises NO_PROVIDER_FOR_ROLE when role maps to None."""
    registry = ProviderRegistry()

    manifest = {
        "agent": {
            "llm": {
                "providers": [],
                "roles": {
                    "primary": None,  # None value
                }
            }
        }
    }

    with pytest.raises(LLMError) as excinfo:
        build_provider_for_role(manifest, "primary", _registry=registry)

    assert excinfo.value.code == "NO_PROVIDER_FOR_ROLE"
    assert "No provider list found for role 'primary'" in excinfo.value.message


def test_get_provider_for_role_unknown_provider_in_list():
    """Role dispatch skips unknown provider names and continues down the list."""
    registry = ProviderRegistry()
    registry.register("ollama", build_success_provider("works"))

    manifest = {
        "agent": {
            "llm": {
                "providers": [
                    {"name": "works", "type": "ollama"},
                    # "unknown" and "also-missing" not in providers
                ],
                "roles": {
                    "primary": ["unknown", "also-missing", "works"],
                }
            }
        }
    }

    provider = build_provider_for_role(manifest, "primary", _registry=registry)
    assert provider._name == "works"


def test_get_provider_for_role_all_unknown_providers():
    """Role dispatch raises ALL_PROVIDERS_FAILED when all providers in list unknown."""
    registry = ProviderRegistry()

    manifest = {
        "agent": {
            "llm": {
                "providers": [
                    {"name": "exists", "type": "ollama"},
                ],
                "roles": {
                    "primary": ["missing1", "missing2"],  # Neither in providers
                }
            }
        }
    }

    with pytest.raises(LLMError) as excinfo:
        build_provider_for_role(manifest, "primary", _registry=registry)

    assert excinfo.value.code == "ALL_PROVIDERS_FAILED"
    assert "Failed to build any provider for role 'primary'" in excinfo.value.message
    # Last error should be from the last attempted provider
    assert "Provider 'missing2' not found in manifest for role 'primary'" in excinfo.value.message


# --------------------------------------------------------------------------- #
# Manifest validation integration tests
# --------------------------------------------------------------------------- #

def test_manifest_validation_rejects_unknown_provider_in_role():
    """Manifest validation rejects roles referencing undeclared provider names."""
    from laew.manifest import ManifestError, load_manifest
    import tempfile
    import yaml

    manifest_data = {
        "version": "1.0.0",
        "system_name": "test",
        "stage": "M15-TEST",
        "workspace": {
            "root": ".",
            "allowed_paths": ["."],
            "restricted_paths": [],
            "ignored_patterns": [],
        },
        "models": {
            "roles": {
                "primary": {"description": "", "context_budget": {}},
                "embedding": {"description": "", "context_budget": {}},
                "reviewer": {"description": "", "context_budget": {}},
            }
        },
        "tools": {
            "categories": {
                "filesystem": {"policy": "read_only_by_default"},
                "git": {"policy": "inspection_first"},
                "terminal": {"policy": "safe_command_allowlist", "allowlist": ["ls"]},
                "web": {"policy": "read_only"},
            }
        },
        "memory": {"session": {}, "second_brain": {}},
        "rag": {"pipeline": {}},
        "agent": {
            "llm": {
                "providers": [
                    {"name": "provider-a", "type": "ollama"},
                    # Note: "provider-b" is referenced in roles but not declared
                ],
                "roles": {
                    "primary": ["provider-a", "provider-b"],  # provider-b not declared
                },
                "retry": {
                    "max_attempts": 3,
                    "backoff_base_ms": 1000,
                    "max_backoff_ms": 5000
                }
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(manifest_data, f)
        manifest_path = f.name

    try:
        # This should raise ManifestError during validation
        with pytest.raises(ManifestError) as excinfo:
            load_manifest(manifest_path)

        assert "references unknown provider 'provider-b'" in str(excinfo.value)
        assert "Declared providers: ['provider-a']" in str(excinfo.value)
    finally:
        import os
        os.unlink(manifest_path)


def test_manifest_validation_passes_when_all_providers_declared():
    """Manifest validation passes when all role providers are declared."""
    from laew.manifest import load_manifest
    import tempfile
    import yaml

    manifest_data = {
        "version": "1.0.0",
        "system_name": "test",
        "stage": "M15-TEST",
        "workspace": {
            "root": ".",
            "allowed_paths": ["."],
            "restricted_paths": [],
            "ignored_patterns": [],
        },
        "models": {
            "roles": {
                "primary": {"description": "", "context_budget": {}},
                "embedding": {"description": "", "context_budget": {}},
                "reviewer": {"description": "", "context_budget": {}},
            }
        },
        "tools": {
            "categories": {
                "filesystem": {"policy": "read_only_by_default"},
                "git": {"policy": "inspection_first"},
                "terminal": {"policy": "safe_command_allowlist", "allowlist": ["ls"]},
                "web": {"policy": "read_only"},
            }
        },
        "memory": {"session": {}, "second_brain": {}},
        "rag": {"pipeline": {}},
        "agent": {
            "llm": {
                "providers": [
                    {"name": "provider-a", "type": "ollama"},
                    {"name": "provider-b", "type": "ollama"},
                ],
                "roles": {
                    "primary": ["provider-a", "provider-b"],  # Both declared
                },
                "retry": {
                    "max_attempts": 3,
                    "backoff_base_ms": 1000,
                    "max_backoff_ms": 5000
                }
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(manifest_data, f)
        manifest_path = f.name

    try:
        # This should succeed
        manifest = load_manifest(manifest_path)
        assert manifest["agent"]["llm"]["roles"]["primary"] == ["provider-a", "provider-b"]
    finally:
        import os
        os.unlink(manifest_path)


# --------------------------------------------------------------------------- #
# CLI integration tests (using actual CLI entry points)
# --------------------------------------------------------------------------- #

def test_chat_command_uses_build_provider_for_role(monkeypatch):
    """CLI chat command uses build_provider_for_role for role-based dispatch."""
    from laew.cli import cmd_chat
    from argparse import Namespace

    # Mock the provider that would be returned
    mock_provider = build_ollama({})
    mock_provider._name = "test-provider"

    # Mock build_provider_for_role to return our mock
    with patch("laew.cli.build_provider_for_role", return_value=mock_provider) as mock_build:
        args = Namespace(
            manifest="manifests/SYSTEM_MANIFEST.yaml",
            model=None,
            base_url=None,
            timeout=None,
            no_persist=True,
            resume=None,
            session=None,
            no_stream=False,
        )

        # We don't need to actually run the chat loop, just verify the provider is built
        # The function will exit early due to mocked input, but we can check the call
        try:
            cmd_chat(args)
        except (EOFError, KeyboardInterrupt):
            # Expected when input() is called in the chat loop
            pass
        except Exception:
            # Other exceptions are okay for this test - we just want to verify the mock was called
            pass

        # Verify build_provider_for_role was called with correct arguments
        mock_build.assert_called_once()
        call_args, call_kwargs = mock_build.call_args
        assert call_args[0] is not None  # manifest
        assert call_args[1] == "primary"  # role
        assert "base_url" in call_kwargs
        assert "timeout" in call_kwargs


def test_multiagent_run_command_uses_build_provider_for_role(monkeypatch):
    """CLI multiagent run command uses build_provider_for_role for role-based dispatch."""
    from laew.cli import cmd_multiagent_run
    from argparse import Namespace

    # Mock the provider that would be returned
    mock_provider = build_ollama({})
    mock_provider._name = "test-provider"

    # Mock both the plan loading and manifest loading to avoid file system dependencies
    with patch("laew.cli.load_multiagent_plan_from_yaml") as mock_load_plan, \
         patch("laew.cli.load_manifest") as mock_load_manifest, \
         patch("laew.cli.build_provider_for_role", return_value=mock_provider) as mock_build:

        # Setup mock returns
        mock_load_plan.return_value = {
            "version": "1.0",
            "agents": {
                "chief": {"role": "primary", "goal": "Test goal"},
                "specialists": []
            }
        }
        mock_load_manifest.return_value = {
            "agent": {
                "llm": {
                    "providers": [{"name": "test-provider", "type": "ollama"}],
                    "roles": {"primary": ["test-provider"]},
                    "retry": {
                        "max_attempts": 3,
                        "backoff_base_ms": 1000,
                        "max_backoff_ms": 5000
                    }
                }
            }
        }

        args = Namespace(
            plan="tests/multiagent/plans/test_agents.yaml",
            manifest="manifests/SYSTEM_MANIFEST.yaml",
            model=None,
            base_url=None,
            provider=None,
            timeout=None,
        )

        # We don't need to actually run the multiagent process, just verify the provider is built
        try:
            cmd_multiagent_run(args)
        except Exception:
            # Exceptions are okay for this test - we just want to verify the mock was called
            pass

        # Verify build_provider_for_role was called with correct arguments
        mock_build.assert_called_once()
        call_args, call_kwargs = mock_build.call_args
        assert call_args[0] is not None  # manifest
        assert call_args[1] == "primary"  # role
        assert "base_url" in call_kwargs
        assert "timeout" in call_kwargs


def test_console_agent_build_uses_build_provider_for_role(monkeypatch):
    """LAEW console agent command uses build_provider_for_role for role-based dispatch."""
    from laew.console.commands.agent import _build_agent
    from laew.console.state import SessionState

    # Mock the provider that would be returned
    mock_provider = build_ollama({})
    mock_provider._name = "test-provider"

    # Mock SessionState to return a basic manifest
    class MockState(SessionState):
        def load_manifest(self):
            return {
                "agent": {
                    "llm": {
                        "providers": [{"name": "test", "type": "ollama"}],
                        "roles": {"primary": ["test"]},
                    }
                }
            }

        def overrides(self):
            return {}

        def manifest_model(self):
            return None

        def conversation_to_messages(self):
            return []

    # Mock build_provider_for_role to return our mock
    with patch("laew.console.commands.agent.build_provider_for_role", return_value=mock_provider) as mock_build:
        state = MockState()
        agent, model_name = _build_agent(state)

        # Verify build_provider_for_role was called with correct arguments
        mock_build.assert_called_once()
        call_args, call_kwargs = mock_build.call_args
        assert call_args[0] is not None  # manifest
        assert call_args[1] == "primary"  # role
        assert "base_url" in call_kwargs
        assert "timeout" in call_kwargs

        # Verify we got the expected provider back
        assert agent.provider._name == "test-provider"


# --------------------------------------------------------------------------- #
# Edge cases and error conditions
# --------------------------------------------------------------------------- #

def test_build_provider_for_role_with_base_url_timeout_overrides():
    """Role-based provider selection respects base_url and timeout overrides."""
    registry = ProviderRegistry()

    def capture_args_builder(cfg, *, base_url=None, timeout=None):
        provider = build_ollama(cfg, base_url=base_url, timeout=timeout)
        provider._captured_base_url = base_url
        provider._captured_timeout = timeout
        return provider

    registry.register("ollama", capture_args_builder)

    manifest = {
        "agent": {
            "llm": {
                "providers": [{"name": "test-provider", "type": "ollama"}],
                "roles": {"primary": ["test-provider"]},
            }
        }
    }

    provider = build_provider_for_role(
        manifest,
        "primary",
        base_url="http://custom:11434",
        timeout=42,
        _registry=registry
    )

    assert provider._captured_base_url == "http://custom:11434"
    assert provider._captured_timeout == 42


def test_build_provider_for_role_manifest_base_url_timeout_used_when_no_override():
    """Role-based provider selection uses manifest values when no CLI overrides."""
    registry = ProviderRegistry()

    def capture_args_builder(cfg, *, base_url=None, timeout=None):
        provider = build_ollama(cfg, base_url=base_url, timeout=timeout)
        provider._captured_base_url = base_url
        provider._captured_timeout = timeout
        return provider

    registry.register("ollama", capture_args_builder)

    manifest = {
        "agent": {
            "llm": {
                "providers": [
                    {
                        "name": "test-provider",
                        "type": "ollama",
                        "host": "custom-host",
                        "port": 9999,
                        "timeout": 100
                    }
                ],
                "roles": {"primary": ["test-provider"]},
            }
        }
    }

    provider = build_provider_for_role(manifest, "primary", _registry=registry)

    # Should use manifest-resolved base_url and timeout
    assert provider._captured_base_url == "http://custom-host:9999"
    assert provider._captured_timeout == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])