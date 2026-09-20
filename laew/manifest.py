from pathlib import Path
from typing import Any

import yaml


class ManifestError(Exception):
    """Raised when the LAEW manifest is invalid."""


REQUIRED_TOP_LEVEL_KEYS = {
    "version",
    "system_name",
    "stage",
    "workspace",
    "models",
    "tools",
    "memory",
    "rag",
}


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a LAEW YAML manifest and return it as a dictionary."""

    manifest_path = Path(path)

    if not manifest_path.is_file():
        raise ManifestError(
            f"Manifest file not found: {manifest_path}"
        )

    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ManifestError(
            f"Invalid YAML in manifest: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ManifestError(
            "Manifest root must be a YAML mapping."
        )

    validate_manifest(data)

    return data


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate the basic structure of a LAEW manifest."""

    missing_keys = REQUIRED_TOP_LEVEL_KEYS - manifest.keys()

    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ManifestError(
            f"Manifest is missing required top-level keys: {missing}"
        )

    mapping_keys = {
        "workspace",
        "models",
        "tools",
        "memory",
        "rag",
    }

    for key in mapping_keys:
        if not isinstance(manifest[key], dict):
            raise ManifestError(
                f"Manifest key '{key}' must be a YAML mapping."
            )

    workspace = manifest["workspace"]

    required_workspace_keys = {
        "root",
        "allowed_paths",
        "restricted_paths",
        "ignored_patterns",
    }

    missing_workspace_keys = (
        required_workspace_keys - workspace.keys()
    )

    if missing_workspace_keys:
        missing = ", ".join(sorted(missing_workspace_keys))
        raise ManifestError(
            f"Manifest workspace is missing required keys: {missing}"
        )

    if not isinstance(workspace["root"], str):
        raise ManifestError(
            "Manifest key 'workspace.root' must be a string."
        )

    for key in ("allowed_paths", "restricted_paths", "ignored_patterns"):
        if not isinstance(workspace[key], list):
            raise ManifestError(
                f"Manifest key 'workspace.{key}' must be a list."
            )

    models = manifest["models"]

    if "roles" not in models:
        raise ManifestError(
            "Manifest key 'models.roles' is required."
        )

    roles = models["roles"]

    if not isinstance(roles, dict):
        raise ManifestError(
            "Manifest key 'models.roles' must be a YAML mapping."
        )

    required_roles = {
        "primary",
        "embedding",
        "reviewer",
    }

    missing_roles = required_roles - roles.keys()

    if missing_roles:
        missing = ", ".join(sorted(missing_roles))
        raise ManifestError(
            f"Manifest models.roles is missing required roles: {missing}"
        )

    for role in required_roles:
        if not isinstance(roles[role], dict):
            raise ManifestError(
                f"Manifest key 'models.roles.{role}' must be a YAML mapping."
            )

    tools = manifest["tools"]

    if "categories" not in tools:
        raise ManifestError(
            "Manifest key 'tools.categories' is required."
        )

    categories = tools["categories"]

    if not isinstance(categories, dict):
        raise ManifestError(
            "Manifest key 'tools.categories' must be a YAML mapping."
        )

    required_categories = {
        "filesystem",
        "git",
        "terminal",
        "web",
    }

    missing_categories = required_categories - categories.keys()

    if missing_categories:
        missing = ", ".join(sorted(missing_categories))
        raise ManifestError(
            f"Manifest tools.categories is missing required categories: {missing}"
        )

    for category in required_categories:
        if not isinstance(categories[category], dict):
            raise ManifestError(
                f"Manifest key 'tools.categories.{category}' "
                "must be a YAML mapping."
            )

    memory = manifest["memory"]

    for key in ("session", "second_brain"):
        if key not in memory:
            raise ManifestError(
                f"Manifest key 'memory.{key}' is required."
            )

        if not isinstance(memory[key], dict):
            raise ManifestError(
                f"Manifest key 'memory.{key}' must be a YAML mapping."
            )

    rag = manifest["rag"]

    if "pipeline" not in rag:
        raise ManifestError(
            "Manifest key 'rag.pipeline' is required."
        )

    if not isinstance(rag["pipeline"], dict):
        raise ManifestError(
            "Manifest key 'rag.pipeline' must be a YAML mapping."
        )

    policies = {
        "filesystem": "read_only_by_default",
        "git": "inspection_first",
        "terminal": "safe_command_allowlist",
        "web": "read_only",
    }

    for category, expected_policy in policies.items():
        tool = categories[category]

        if "policy" not in tool:
            raise ManifestError(
                f"Manifest key 'tools.categories.{category}.policy' is required."
            )

        policy = tool["policy"]

        if not isinstance(policy, str):
            raise ManifestError(
                f"Manifest key 'tools.categories.{category}.policy' "
                "must be a string."
            )

        if policy != expected_policy:
            raise ManifestError(
                f"Manifest key 'tools.categories.{category}.policy' "
                f"has invalid policy: {policy}"
            )

    terminal = categories["terminal"]

    if "allowlist" not in terminal:
        raise ManifestError(
            "Manifest key 'tools.categories.terminal.allowlist' is required."
        )

    if not isinstance(terminal["allowlist"], list):
        raise ManifestError(
            "Manifest key 'tools.categories.terminal.allowlist' must be a list."
        )

    if "agent" in manifest:
        agent = manifest["agent"]
        if not isinstance(agent, dict):
            raise ManifestError("Manifest key 'agent' must be a YAML mapping.")
        if "llm" not in agent or not isinstance(agent["llm"], dict):
            raise ManifestError("Manifest key 'agent.llm' must be a YAML mapping.")
        if "providers" not in agent["llm"] or not isinstance(
            agent["llm"]["providers"], list
        ):
            raise ManifestError("Manifest key 'agent.llm.providers' must be a list.")
        if "retry" not in agent["llm"] or not isinstance(agent["llm"]["retry"], dict):
            raise ManifestError("Manifest key 'agent.llm.retry' must be a YAML mapping.")

        providers = agent["llm"]["providers"]
        for idx, provider in enumerate(providers):
            if not isinstance(provider, dict):
                raise ManifestError(
                    f"Manifest key 'agent.llm.providers[{idx}]' must be a YAML mapping."
                )

            ptype = provider.get("type")
            if not isinstance(ptype, str) or not ptype.strip():
                raise ManifestError(
                    f"Manifest key 'agent.llm.providers[{idx}].type' is required and must be a non-empty string."
                )

            timeout = provider.get("timeout")
            if timeout is not None:
                if not isinstance(timeout, int) or isinstance(timeout, bool):
                    raise ManifestError(
                        f"Manifest key 'agent.llm.providers[{idx}].timeout' must be a positive integer."
                    )
                if timeout <= 0:
                    raise ManifestError(
                        f"Manifest key 'agent.llm.providers[{idx}].timeout' must be a positive integer."
                    )

        # Validate agent.llm.roles if present
        if "llm" in agent:
            llm = agent["llm"]
            if "roles" in llm and llm["roles"] is not None:
                roles = llm["roles"]
                if not isinstance(roles, dict):
                    raise ManifestError(
                        "Manifest key 'agent.llm.roles' must be a YAML mapping."
                    )
                # Get provider names from the providers list for validation
                provider_names = {p.get("name") for p in llm.get("providers", []) if p.get("name")}
                for role, provider_list in roles.items():
                    if not isinstance(role, str) or not role.strip():
                        raise ManifestError(
                            f"Manifest key 'agent.llm.roles' keys must be non-empty strings (invalid role: '{role}')"
                        )
                    if not isinstance(provider_list, list):
                        raise ManifestError(
                            f"Manifest key 'agent.llm.roles[{role}]' must be a list of provider names."
                        )
                    if not provider_list:
                        raise ManifestError(
                            f"Manifest key 'agent.llm.roles[{role}]' must be a non-empty list."
                        )
                    for provider_name in provider_list:
                        if not isinstance(provider_name, str) or not provider_name.strip():
                            raise ManifestError(
                                f"Manifest key 'agent.llm.roles[{role}]' contains an empty or non-string provider name."
                            )
                        if provider_name not in provider_names:
                            raise ManifestError(
                                f"Manifest key 'agent.llm.roles[{role}]' references unknown provider '{provider_name}'. "
                                f"Declared providers: {sorted(provider_names)}"
                            )
