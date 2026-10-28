"""Explicit, non-destructive migration of a legacy project collection."""

from pathlib import Path

import numpy as np

from laew.rag.identity import canonical_project_path, project_collection_name
from laew.rag.vector_store import _build_chroma_client


def migrate_legacy_project(config: dict, project_root: str, *, confirmed_owner: str) -> dict:
    """Copy a legacy collection only after the operator explicitly names its owner.

    Existing destination records must be an exact subset of the source, so an
    interrupted migration can be retried without overwriting unrelated data.
    The source collection is never modified.
    """
    if not project_root or not confirmed_owner or (
        canonical_project_path(project_root) != canonical_project_path(confirmed_owner)
    ):
        raise ValueError("Explicit matching project ownership confirmation is required.")
    if not Path(project_root).is_dir():
        raise ValueError("The confirmed project directory does not exist.")
    import chromadb

    client = _build_chroma_client(chromadb, config.get("host", "localhost"),
                                  int(config.get("port", 8000)), int(config.get("timeout", 30)))
    legacy_name = config.get("project_collection", "laew_project")
    target_name = project_collection_name(project_root)
    if legacy_name == target_name or target_name == config.get("global_collection", "laew_global"):
        raise ValueError("Source and destination collections must be distinct.")
    source = client.get_collection(legacy_name)
    source_metadata = dict(source.metadata or {})
    if not source_metadata.get("embedding_model_id"):
        raise ValueError("Legacy embedding identity is missing; migration cannot be verified safely.")
    records = source.get(include=["embeddings", "metadatas", "documents"])
    ids = list(records["ids"])
    embeddings = records["embeddings"]
    metadata = records["metadatas"]
    documents = records["documents"]
    if any(not m or m.get("source") != "project" for m in metadata):
        raise ValueError("Legacy collection contains records without unambiguous project scope.")
    # Do not use get_or_create with source metadata: Chroma versions differ in
    # whether that changes metadata on an existing destination.
    try:
        target = client.get_collection(target_name)
    except Exception as exc:
        # Avoid treating network or permission failures as a missing collection.
        if type(exc).__name__ not in {"NotFoundError", "InvalidCollectionException"}:
            raise
        target = client.create_collection(target_name, metadata=source_metadata)
    if (target.metadata or {}).get("embedding_model_id") != source_metadata["embedding_model_id"]:
        raise ValueError("Destination embedding identity differs from the legacy collection.")
    existing = target.get(include=["embeddings", "metadatas", "documents"])
    source_index = {record_id: i for i, record_id in enumerate(ids)}
    for j, record_id in enumerate(existing["ids"]):
        i = source_index.get(record_id)
        if (i is None or existing["metadatas"][j] != metadata[i]
                or existing["documents"][j] != documents[i]
                or not np.array_equal(existing["embeddings"][j], embeddings[i])):
            raise ValueError("Destination contains different data; migration stopped without overwriting it.")
    existing_ids = set(existing["ids"])
    missing = [i for i, record_id in enumerate(ids) if record_id not in existing_ids]
    if missing:
        kwargs = {"ids": [ids[i] for i in missing],
                  "embeddings": [list(embeddings[i]) for i in missing],
                  "metadatas": [metadata[i] for i in missing]}
        # Chroma accepts None documents for legacy records with no document field.
        if all(documents[i] is not None for i in missing):
            kwargs["documents"] = [documents[i] for i in missing]
        target.add(**kwargs)
    check = target.get(include=["embeddings", "metadatas", "documents"])
    indices = {record_id: i for i, record_id in enumerate(check["ids"])}
    if set(indices) != set(ids):
        raise RuntimeError("Migration verification failed: record IDs differ; retry after inspection.")
    for i, record_id in enumerate(ids):
        j = indices[record_id]
        if (check["metadatas"][j] != metadata[i] or check["documents"][j] != documents[i]
                or not np.array_equal(check["embeddings"][j], embeddings[i])):
            raise RuntimeError("Migration verification failed: destination content differs; source is intact.")
    if ids:
        query = target.query(query_embeddings=[list(embeddings[0])], n_results=1)
        if not query.get("ids") or not query["ids"][0]:
            raise RuntimeError("Migration verification failed: destination retrieval returned no result.")
    return {"source": legacy_name, "destination": target_name, "records": len(ids),
            "copied": len(missing), "source_preserved": True}
