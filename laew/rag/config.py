"""Resolve manifest knowledge roots within the trusted workspace aliases."""

from pathlib import Path
from typing import Any, Optional

from laew.security.path_resolver import PathResolver


def manifest_base_dir(manifest_path: str | Path) -> Path:
    """Return the project directory that anchors a relative manifest path."""
    path = Path(manifest_path).expanduser()
    if not path.is_absolute():
        return Path.cwd().resolve()
    path = path.resolve()
    if path.parent.name.casefold() == "manifests":
        return path.parent.parent
    return path.parent


def resolve_project_root(
    manifest: dict[str, Any],
    *,
    base_dir: Optional[str | Path] = None,
    project_root: Optional[str | Path] = None,
) -> Path:
    """Resolve the manifest's project root, anchoring relative values safely."""
    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    configured = (manifest.get("workspace", {}) or {}).get("root", ".") or "."
    path = Path(configured).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path(base_dir or Path.cwd()).expanduser().resolve() / path).resolve()


def resolve_knowledge_root(
    manifest: dict[str, Any],
    *,
    project_root: str | Path,
    projects_root: Optional[str | Path] = None,
    knowledge_root: Optional[str | Path] = None,
) -> Path:
    """Resolve the configured vault path without allowing it outside @knowledge.

    The historical value ``knowledge`` means the global vault root. Other
    relative values are interpreted under that trusted root; explicit aliases
    are resolved by :class:`PathResolver`. Absolute paths are allowed only when
    they remain inside the configured @knowledge boundary.
    """
    resolver = PathResolver(
        project_root=project_root,
        projects_root=projects_root,
        knowledge_root=knowledge_root,
    )
    second_brain = (manifest.get("memory", {}) or {}).get("second_brain", {}) or {}
    configured = second_brain.get("path") or "@knowledge"
    if not isinstance(configured, (str, Path)):
        raise ValueError("memory.second_brain.path must be a path or @knowledge alias.")
    value = str(configured).strip().replace("\\", "/")
    if not value or value.casefold() == "knowledge":
        value = "@knowledge"

    path = Path(value).expanduser()
    if path.is_absolute():
        resolved = path.resolve()
        if not resolver.is_within_root(resolved, PathResolver.ALIAS_KNOWLEDGE):
            raise ValueError("The configured knowledge path must remain inside @knowledge.")
        return resolved

    alias_path = value if value.startswith("@") else f"@knowledge/{value}"
    resolved = resolver.resolve(alias_path)
    if not resolver.is_within_root(resolved, PathResolver.ALIAS_KNOWLEDGE):
        raise ValueError("The configured knowledge path must remain inside @knowledge.")
    return resolved
