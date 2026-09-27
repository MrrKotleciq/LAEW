"""Shared configuration constants for LAEW.

This module centralizes configuration values that appear in multiple
locations, making them easy to update and document.

All values here are considered configuration, not implementation details.
"""

# Context budget configuration (Milestone 14 / ADR-004)
CONTEXT_BUDGET_SYSTEM_TOKENS = 2000
CONTEXT_BUDGET_CONVERSATION_TOKENS = 4000
CONTEXT_BUDGET_RAG_TOKENS = 8000
CONTEXT_BUDGET_TOOLS_TOKENS = 4000
CONTEXT_BUDGET_TOTAL_TOKENS = 18000
CONTEXT_BUDGET_RESERVED_TOKENS = 2000

# Token estimation (Milestone 14 / ADR-004)
CHARS_PER_TOKEN_DEFAULT = 4.0

# RAG configuration
RAG_CHUNK_SIZE = 1000
RAG_CHUNK_OVERLAP = 200
RAG_MAX_CONTEXT_TOKENS = 8000

# Infrastructure defaults
DEFAULT_VECTOR_STORE_PORT = 8000
DEFAULT_TOOL_TERMINAL_TIMEOUT_MS = 30000
