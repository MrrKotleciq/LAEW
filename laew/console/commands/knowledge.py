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


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def _manifest_knowledge_cfg(state: SessionState) -> dict:
    """Collect the Obsidian vault configuration the manifest declares.

    The embedding model is read from ``models.roles.embedding.model_name`` when
    the manifest declares one; ``knowledge stats`` indexes the vault and needs
    it. When the manifest omits the embedding role, this falls back to
    ``"nomic-embed-text"`` — a valid default per the session resolution order
    (manifest role, then hardcoded default). The manifest declares
    ``bge-m3:latest`` (1024-dim), so this default only applies to manifests
    without an embedding role.
    """
    manifest = state.load_manifest()
    # The Second Brain config lives under ``memory.second_brain`` (the manifest
    # declares it there and validates it as a mapping), not under ``memory``
    # directly — matching how ``rag.py`` reads the same knowledge root.
    second_brain = ((manifest.get("memory", {}) or {}).get("second_brain", {}) or {})
    return {
        "project_root": (manifest.get("workspace", {}) or {}).get("root", "."),
        "knowledge_root": second_brain.get("path", "knowledge"),
        "structure": second_brain.get("structure") or [],
        "embedding_model": (
            (manifest.get("models", {}) or {}).get("roles", {}) or {}
        ).get("embedding", {}).get("model_name")
        or "nomic-embed-text",
    }


def _cmd_list(args: list, state: SessionState) -> int:
    """knowledge list — show vault structure and note counts per folder."""
    from laew.rag.knowledge_base import KnowledgeBase

    cfg = _manifest_knowledge_cfg(state)
    kb = KnowledgeBase(
        project_root=cfg["project_root"],
        knowledge_root=cfg["knowledge_root"],
        embedding_service=_noop_embedding(),
    )
    structure = kb.structure()

    print(f"Second Brain vault: {cfg['knowledge_root']}/")
    print("-" * 60)

    total = 0
    for folder, count in structure.items():
        total += count
        print(f"  {folder}/  ({count} notes)")

    print("-" * 60)
    print(f"Total: {total} note(s) across {len(structure)} folder(s)")
    return 0


def _cmd_show(args: list, state: SessionState) -> int:
    """knowledge show <path> — show a note's frontmatter, tags and body."""
    from laew.rag.obsidian import parse_note

    cfg = _manifest_knowledge_cfg(state)
    knowledge_root = Path(cfg["knowledge_root"])

    if not args:
        return _err("usage: knowledge show <note-path>")

    target = args[0]
    path = knowledge_root / target if not Path(target).is_absolute() else Path(target)
    if not path.exists():
        return _err(f"note not found: {target}")

    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError) as e:
        return _err(f"could not read note: {e}")

    note = parse_note(content)
    print(f"note: {path.relative_to(knowledge_root)}")
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
    from laew.rag.embedding import OllamaEmbedding
    from laew.rag.knowledge_base import KnowledgeBase

    cfg = _manifest_knowledge_cfg(state)
    kb = KnowledgeBase(
        project_root=cfg["project_root"],
        knowledge_root=cfg["knowledge_root"],
        embedding_service=OllamaEmbedding(model=cfg["embedding_model"]),
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
