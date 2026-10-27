"""knowledge command — inspect and manage the Obsidian Second Brain vault.

Realizes the ``@knowledge`` scope (ADR-011) in the console:

  knowledge list         Show vault structure (folders + note counts).
  knowledge show <path>  Show a note's frontmatter, tags, backlinks and body.
  knowledge stats        Show vault files and the @knowledge RAG chunk counts.

The vault is indexed into the ``@knowledge`` RAG scope by ``rag embed``; these
subcommands inspect the vault and its index. Offline-friendly: ``list`` and
``show`` need no embedding service.
"""

from pathlib import Path
from typing import Callable, Dict

from laew.console.state import SessionState
from laew.rag.config import manifest_base_dir, resolve_knowledge_root, resolve_project_root


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def _manifest_knowledge_cfg(manifest: dict, state: SessionState) -> dict:
    """Collect the Obsidian vault configuration the manifest declares.

    Embedding selection for ``knowledge stats`` is handled by
    :func:`laew.runtime.build_embedding_service`, which reads
    ``models.roles.embedding.type``. This helper only
    supplies the vault path/structure the read-only commands need.
    """
    # The Second Brain config lives under ``memory.second_brain`` (the manifest
    # declares it there and validates it as a mapping), not under ``memory``
    # directly — matching how ``rag.py`` reads the same knowledge root.
    second_brain = ((manifest.get("memory", {}) or {}).get("second_brain", {}) or {})
    project_root = resolve_project_root(
        manifest, base_dir=manifest_base_dir(state.manifest_path)
    )
    return {
        "project_root": project_root,
        "knowledge_root": resolve_knowledge_root(
            manifest, project_root=project_root
        ),
        "structure": second_brain.get("structure") or [],
    }


def _cmd_list(args: list, state: SessionState) -> int:
    """knowledge list — show vault structure and note counts per folder."""
    from laew.rag.knowledge_base import KnowledgeBase

    manifest = state.load_manifest()
    cfg = _manifest_knowledge_cfg(manifest, state)
    kb = KnowledgeBase(
        project_root=cfg["project_root"],
        knowledge_root=cfg["knowledge_root"],
        embedding_service=_noop_embedding(),
    )
    vault_root = Path(cfg["knowledge_root"])
    if not vault_root.is_dir():
        return _err(f"@knowledge vault is unavailable: {vault_root}")
    structure = kb.structure()

    print(f"Second Brain vault: {cfg['knowledge_root']}/")
    print("-" * 60)

    total = 0
    expected = cfg["structure"]
    folders = list(dict.fromkeys([*expected, *structure.keys()]))
    for folder in folders:
        count = structure.get(folder, 0)
        total += count
        print(f"  {folder}/  ({count} notes)")

    print("-" * 60)
    print(f"Total: {total} note(s) across {len(structure)} folder(s)")
    return 0


def _cmd_show(args: list, state: SessionState) -> int:
    """knowledge show <path> — show a note's frontmatter, tags and body."""
    from laew.rag.obsidian import parse_note

    manifest = state.load_manifest()
    cfg = _manifest_knowledge_cfg(manifest, state)
    knowledge_root = Path(cfg["knowledge_root"]).resolve()

    if not args:
        return _err("usage: knowledge show <note-path>")

    target = args[0]
    if target.startswith("@"):
        if not (
            target == "@knowledge"
            or target.startswith("@knowledge/")
            or target.startswith("@knowledge\\")
        ):
            return _err("knowledge show only accepts paths inside @knowledge")
        target = target[len("@knowledge"):].lstrip("/\\")
    path = Path(target).expanduser()
    if not knowledge_root.is_dir():
        return _err(f"@knowledge vault is unavailable: {knowledge_root}")
    if not path.is_absolute():
        path = knowledge_root / path
    path = path.resolve()
    try:
        path.relative_to(knowledge_root)
    except ValueError:
        return _err("knowledge show path escapes the configured @knowledge vault")
    if not path.is_file():
        return _err(f"note not found: {target}")

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _err(f"could not read note: {e}")

    note = parse_note(content)
    print(f"note: @knowledge/{path.relative_to(knowledge_root).as_posix()}")
    print("-" * 60)

    if note["title"]:
        print(f"title: {note['title']}")
    if note["tags"]:
        print(f"tags: {' '.join(note['tags'])}")
    if note["backlinks"]:
        print(f"backlinks: {' '.join(note['backlinks'])}")
    print("-" * 60)
    print(note["body"])
    return 0


def _cmd_stats(args: list, state: SessionState) -> int:
    """knowledge stats — show vault files and the @knowledge chunk counts."""
    from laew.rag.knowledge_base import KnowledgeBase
    from laew.runtime import build_embedding_service

    manifest = state.load_manifest()
    cfg = _manifest_knowledge_cfg(manifest, state)
    try:
        embedding = build_embedding_service(manifest)
    except (ValueError, RuntimeError) as e:
        print(f"[!] embedding configuration unavailable: {e}")
        return 1
    kb = KnowledgeBase(
        project_root=cfg["project_root"],
        knowledge_root=cfg["knowledge_root"],
        embedding_service=embedding,
    )

    structure = kb.structure()
    print(f"Second Brain vault: {cfg['knowledge_root']}/")
    print("-" * 60)
    total = sum(structure.values())
    for folder, count in structure.items():
        print(f"  {folder}/  ({count} notes)")
    print("-" * 60)
    print(f"vault notes: {total}")

    try:
        kb.load_vault(force=True)
    except Exception as e:
        print(f"[!] could not index vault: {e}")
        print("[!] is the embedding model running? (rag embed to retry)")
        return 1

    print(
        f"@knowledge store: {kb.global_store.count()} chunk(s) indexed"
    )
    return 0


def _noop_embedding():
    """Return a minimal embedding service for read-only vault inspection.

    ``list`` does not need real embeddings; it only reads the directory tree.
    """
    class _Noop:
        def embed(self, _text: str) -> list:
            return []

        def embed_batch(self, _texts: list) -> list:
            return []

    return _Noop()


def _dispatch(args: list, state: SessionState) -> int:
    """knowledge list|show|stats — inspect the Obsidian Second Brain vault."""
    sub = args[0] if args else "list"
    if sub == "list":
        return _cmd_list(args[1:], state)
    if sub == "show":
        return _cmd_show(args[1:], state)
    if sub == "stats":
        return _cmd_stats(args[1:], state)
    return _err(f"unknown knowledge subcommand: {sub} (list|show|stats)")


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {"knowledge": _dispatch}
