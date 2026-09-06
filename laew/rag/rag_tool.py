"""RAG tool for agent knowledge retrieval."""

from typing import Any, Dict, List, Optional

from laew.agent.base import AgentError
from laew.prompts.context_budget import ContextBudget
from laew.rag.knowledge_base import KnowledgeScope
from laew.rag.pipeline import RAGPipeline, RAGResult
from laew.tools.base import Tool, ToolResult


class RagTool(Tool):
    """
    Tool for querying the RAG knowledge base.

    Enables agents to retrieve relevant information from project memory
    and global knowledge sources using semantic search.
    """

    name = "rag"
    description = (
        "Query the knowledge base using semantic search. "
        "Supports project-scoped, global-scoped, and hybrid-scoped retrieval. "
        "Returns relevant context with source attribution."
    )

    def __init__(
        self,
        pipeline: RAGPipeline,
        context_budget: ContextBudget,
    ):
        """
        Initialize RAG tool.

        Args:
            pipeline: RAG pipeline for executing queries
            context_budget: Context budget for token management
        """
        super().__init__()
        self._pipeline = pipeline
        self._context_budget = context_budget

    def validate(self, operation: str, **kwargs) -> tuple[bool, Optional[str]]:
        """
        Validate operation before execution.

        Args:
            operation: Operation name (should be 'query')
            **kwargs: Operation arguments

        Returns:
            Tuple of (is_valid, error_message)
        """
        if operation != "query":
            return False, f"Unsupported operation: {operation}"

        query = kwargs.get("query")
        if not query or not isinstance(query, str):
            return False, "Query must be a non-empty string"

        scope_str = kwargs.get("scope", "project")
        try:
            KnowledgeScope(scope_str)
        except ValueError:
            valid_scopes = [s.value for s in KnowledgeScope]
            return False, f"Invalid scope: {scope_str}. Valid scopes: {valid_scopes}"

        max_results = kwargs.get("max_results")
        if max_results is not None:
            if not isinstance(max_results, int) or max_results <= 0:
                return False, "max_results must be a positive integer"

        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        """
        Execute RAG query operation.

        Args:
            operation: Operation name (should be 'query')
            **kwargs: Operation arguments (query, scope, max_results)

        Returns:
            ToolResult with retrieved context and metadata
        """
        if operation != "query":
            return ToolResult.error(
                code="ERR_INVALID_OPERATION",
                message=f"Unsupported operation: {operation}",
            )

        query = kwargs["query"]
        scope_str = kwargs.get("scope", "project")
        max_results = kwargs.get("max_results")

        try:
            scope = KnowledgeScope(scope_str)
            result = self._pipeline.retrieve(
                query=query,
                scope=scope,
                top_k=max_results,
            )

            # Format result for agent consumption
            if not result.context:
                data = {
                    "context": "",
                    "sources": [],
                    "total_tokens": 0,
                    "message": "No relevant information found in knowledge base.",
                }
            else:
                data = {
                    "context": result.context,
                    "sources": result.sources,
                    "total_tokens": result.total_tokens,
                    "chunk_count": len(result.chunks),
                    "query": result.query,
                    "scope": result.scope.value,
                }

            return ToolResult.ok(data=data)

        except Exception as e:
            return ToolResult.error(
                code="ERR_RAG_FAILURE",
                message=f"RAG query failed: {str(e)}",
            )