"""RAG command handlers for the LAEW testing console.

Exercises the RAG pipeline against the manifest's memory configuration:
``rag query`` runs retrieval, ``rag embed`` synchronizes knowledge, and
``rag stats`` reports vector-store counts.  Offline-friendly: a dead embedding
endpoint is surfaced as a visible ``[!]`` (the pipeline records the error on
the result) rather than crashing the REPL.
"""

from typing import Callable, Dict, Optional

from laew.console.state import SessionState
from laew.rag.config import manifest_base_dir, resolve_knowledge_root, resolve_project_root
from laew.rag.knowledge_base import KnowledgeBase, KnowledgeScope
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import ChromaVectorStore

#: ``scope=`` values accepted by ``rag query`` (mirror KnowledgeScope values).
#: ``knowledge`` is an alias for ``global`` — the ADRs (ADR-002/ADR-011) name
#: the global store ``@knowledge`` while the enum calls it ``global``.
SCOPE_ALIASES = {
    "project": KnowledgeScope.PROJECT,
    "global": KnowledgeScope.GLOBAL,
    "knowledge": KnowledgeScope.GLOBAL,
    "hybrid": KnowledgeScope.HYBRID,
}


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def _manifest_rag_config(manifest: dict, state: SessionState) -> dict:
    """Collect the RAG configuration the manifest declares (best-effort)."""
    project_root = resolve_project_root(
        manifest, base_dir=manifest_base_dir(state.manifest_path)
    )
    knowledge_root = resolve_knowledge_root(
        manifest, project_root=project_root
    )

    pipeline_cfg = manifest.get("rag", {}).get("pipeline", {})
    top_k = int(pipeline_cfg.get("top_k", 5))
    max_context_tokens = int(pipeline_cfg.get("max_context_tokens", 8000))

    vector_store_config = manifest.get("rag", {}).get("vector_store", {})
    project_sources = manifest.get("rag", {}).get("project_sources", {}) or {}

    return {
        "project_root": str(project_root),
        "knowledge_root": str(knowledge_root),
        "top_k": top_k,
        "max_context_tokens": max_context_tokens,
        "vector_store_config": vector_store_config,
        "project_source_allowlist": project_sources.get("allowlist"),
    }


def _build_pipeline(state: SessionState) -> RAGPipeline:
    """Build the session RAG pipeline from the manifest config."""
    from laew.runtime import build_embedding_service

    manifest = state.load_manifest()
    cfg = _manifest_rag_config(manifest, state)
    embedding = build_embedding_service(manifest)
    kb = KnowledgeBase(
        project_root=cfg["project_root"],
        knowledge_root=cfg["knowledge_root"],
        embedding_service=embedding,
        vector_store_config=cfg["vector_store_config"],
        project_source_allowlist=cfg["project_source_allowlist"],
    )
    pipeline = RAGPipeline(
        knowledge_base=kb,
        embedding_service=embedding,
        top_k=cfg["top_k"],
        max_context_tokens=cfg["max_context_tokens"],
    )
    return pipeline


def cmd_rag_query(args: list, state: SessionState) -> int:
    """rag query "<query>" [scope=project|global|hybrid] [k=top_k]."""
    query_parts = []
    scope = KnowledgeScope.PROJECT
    top_k = None
    for item in args:
        if item.startswith("scope="):
            alias = item.split("=", 1)[1].lower()
            scope = SCOPE_ALIASES.get(alias)
            if scope is None:
                return _err(f"unknown scope '{alias}' (project|global|knowledge|hybrid)")
        elif item.startswith("k="):
            try:
                top_k = max(1, int(item.split("=", 1)[1]))
            except ValueError:
                return _err(f"invalid k value '{item.split('=', 1)[1]}'")
        else:
            query_parts.append(item)
    if not query_parts:
        return _err('usage: rag query "<query>" [scope=project|global|knowledge|hybrid] [k=5]')
    query = " ".join(query_parts)

    try:
        pipeline = _build_pipeline(state)
        result = pipeline.retrieve(query, scope=scope, top_k=top_k)
    except Exception as e:
        return _err(f"RAG query failed: {e}")

    if result.error:
        print(f"[!] retrieval error: {result.error}")
        print("[!] is the embedding model running? (rag stats to inspect stores)")
        return 1

    print(f"[OK] {len(result.chunks)} chunk(s) | scope={result.scope.value}"
          f" | {result.total_tokens} tokens | sources: {len(result.sources)}")
    for source in sorted(result.sources):
        print(f"  - {source}")
    if result.context:
        print("---")
        print(result.context[:1200])
    return 0


def cmd_rag_embed(args: list, state: SessionState) -> int:
    """rag embed [force] — synchronize project and global knowledge."""
    force = bool(args) and args[0] == "force"
    try:
        pipeline = _build_pipeline(state)
        changes = pipeline.knowledge_base.synchronize(force=force)
    except Exception as e:
        return _err(f"embedding/load failed: {e}")
    stats = pipeline.knowledge_base.count_chunks()
    for scope, categories in changes.items():
        for category, counts in categories.items():
            print(f"{scope} {category}: {counts['documents']} document(s), {counts['chunks']} chunk(s)")
    print(f"[OK] knowledge loaded (project+global: {stats} chunks)")
    return 0


def cmd_rag_stats(args: list, state: SessionState) -> int:
    """rag stats — report pipeline and vector-store configuration."""
    try:
        pipeline = _build_pipeline(state)
    except Exception as e:
        return _err(f"could not build pipeline: {e}")
    stats = pipeline.get_stats()
    kb = pipeline.knowledge_base
    print(f"pipeline top_k: {stats['top_k']}")
    print(f"max_context_tokens: {stats['max_context_tokens']}")
    print(f"similarity_threshold: {stats['similarity_threshold']}")
    print(f"project store: {stats['project_chunks']} chunk(s)")
    print(f"global store: {stats['global_chunks']} chunk(s)")
    project_type = type(kb.project_store).__name__
    global_type = type(kb.global_store).__name__
    project_persistent = isinstance(kb.project_store, ChromaVectorStore)
    global_persistent = isinstance(kb.global_store, ChromaVectorStore)
    if project_type == global_type:
        print(
            f"backend: {project_type} "
            f"(persistent: {project_persistent and global_persistent})"
        )
    else:
        print(
            f"backend: project={project_type}, global={global_type} "
            f"(persistent: project={project_persistent}, global={global_persistent})"
        )
    return 0


def _dispatch(args: list, state: SessionState) -> int:
    """
    rag query|embed|stats — drive the RAG pipeline against the manifest's
    memory configuration.

    Examples:
      rag query "tool approval gates" scope=project k=5
      rag embed force
      rag stats

    See also: 'agent run', 'prompt show rag'.
    """
    sub = args[0] if args else "stats"
    if sub == "query":
        return cmd_rag_query(args[1:], state)
    if sub == "embed":
        return cmd_rag_embed(args[1:], state)
    if sub == "stats":
        return cmd_rag_stats(args[1:], state)
    return _err(f"unknown rag subcommand: {sub} (query|embed|stats)")


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {"rag": _dispatch}
