"""Per-project settings stored alongside the project, independent of sessions."""

import json
import os
import tempfile
from pathlib import Path, PurePosixPath

LANGUAGES = {"en": "English", "pl": "Polish"}
CONFIG_NAME = ".laew-project.json"


def validate_rag_source_allowlist(value: object) -> list[str]:
    """Validate optional project-relative Markdown glob patterns.

    Patterns select content, not filesystem permissions. Hidden paths and other
    ingestion exclusions still apply; a project cannot change the global vault.
    """
    if not isinstance(value, list) or not value:
        raise ValueError("rag_source_allowlist must be a non-empty list of Markdown patterns.")
    for pattern in value:
        if (not isinstance(pattern, str) or not pattern.endswith(".md")
                or "\\" in pattern or ":" in pattern
                or PurePosixPath(pattern).is_absolute()
                or any(part in ("", ".", "..") for part in pattern.split("/"))):
            raise ValueError("rag_source_allowlist requires relative POSIX Markdown patterns without traversal.")
    return list(value)


def validate_language(value):
    if not isinstance(value, str) or value not in LANGUAGES:
        raise ValueError("Unsupported documentation language; choose en or pl.")
    return value


def project_overrides(project_root):
    path = Path(project_root).resolve() / CONFIG_NAME
    if path.is_symlink():
        raise ValueError("Project settings cannot be a symbolic link.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Project settings are not valid UTF-8 JSON.") from exc
    if not isinstance(data, dict):
        raise ValueError("Project settings must be a JSON object.")
    if "rag_source_allowlist" in data:
        data["rag_source_allowlist"] = validate_rag_source_allowlist(data["rag_source_allowlist"])
    if 'documentation_language' in data: validate_language(data['documentation_language'])
    return data


def load_project_settings(project_root, defaults=None):
    return {"documentation_language":"en", **(defaults or {}), **project_overrides(project_root)}


def save_project_settings(project_root, updates):
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project root is not a directory.")
    data = project_overrides(root)
    for key,value in updates.items():
        if value is None and key == "documentation_language": data.pop(key,None)
        else: data[key]=value
    if 'documentation_language' in data: validate_language(data['documentation_language'])
    if "rag_source_allowlist" in data:
        data["rag_source_allowlist"] = validate_rag_source_allowlist(data["rag_source_allowlist"])
    path = root / CONFIG_NAME
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, prefix=".laew-settings-", delete=False) as handle:
            temp_name = handle.name
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return data


def save_project_language(project_root, language):
    return save_project_settings(project_root, {"documentation_language": validate_language(language)})
