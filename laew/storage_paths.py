"""Shared path and namespace rules for canonical application stores."""

import hashlib
from pathlib import Path


def memory_storage_path(conversation_directory, override=None):
    return Path(override) if override else Path(conversation_directory).parent / 'memory' / 'memory.db'


def knowledge_storage_path(conversation_directory, override=None):
    return Path(override) if override else Path(conversation_directory).parent / 'knowledge' / 'curation.db'


def memory_collection_name(storage_override=None):
    if not storage_override:
        return 'laew_long_term_memory'
    path_digest = hashlib.sha256(str(Path(storage_override).resolve()).encode()).hexdigest()
    return 'laew_ltm_' + path_digest[:16]
