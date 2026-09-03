"""Web operations tool wrapper (tools/web/CONTRACT.md)."""

from typing import Optional
from urllib.parse import urlparse

from laew.tools.base import ErrorCode, Tool, ToolResult


class WebTool(Tool):
    """
    Web operations tool with security compliance (P8 / ADR-006).

    Implements tools/web/CONTRACT.md.

    Operations:
        - search_web: Search technical documentation (read-only)
        - read_url_content: Fetch and convert URL to Markdown (read-only)
    """

    def __init__(self):
        """Initialize web tool."""
        super().__init__(requires_approval=False)

    def validate(self, operation: str, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate operation input."""
        valid_ops = {"search_web", "read_url_content"}
        if operation not in valid_ops:
            return False, f"Unknown operation: {operation}"
        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        """Execute web operation."""
        if operation == "search_web":
            return self._search_web(**kwargs)
        elif operation == "read_url_content":
            return self._read_url_content(**kwargs)
        return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, f"Unknown operation: {operation}")

    def search_web(self, query: str, domain: Optional[str] = None) -> ToolResult:
        """Public interface for search_web operation."""
        return self.call("search_web", query=query, domain=domain)

    def read_url_content(self, url: str) -> ToolResult:
        """Public interface for read_url_content operation."""
        return self.call("read_url_content", url=url)

    def _validate_url_protocol(self, url: str) -> tuple[bool, Optional[str]]:
        """Validate that URL uses http or https protocol."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                return False, f"Unsupported protocol: {parsed.scheme}"
            if not parsed.netloc:
                return False, "Invalid URL: missing domain"
            return True, None
        except Exception as e:
            return False, str(e)

    def _search_web(self, query: str, domain: Optional[str] = None) -> ToolResult:
        """Search web for technical documentation."""
        if not query or not isinstance(query, str):
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, "query must be a non-empty string")

        try:
            # Import requests locally to avoid hard dependency
            import requests
        except ImportError:
            return ToolResult.error(
                ErrorCode.ERR_INVALID_INPUT,
                "requests library not available for web search"
            )

        try:
            # Build search query
            search_query = query
            if domain:
                search_query = f"{query} site:{domain}"

            # Use DuckDuckGo API (no authentication needed)
            # Note: This is a simple implementation. Production would use proper search API.
            url = "https://api.duckduckgo.com/"
            params = {
                "q": search_query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Parse results
            results = []

            # Add related topics as results
            if "RelatedTopics" in data:
                for topic in data["RelatedTopics"][:5]:  # Limit to 5 results
                    if isinstance(topic, dict) and "FirstURL" in topic:
                        results.append({
                            "title": topic.get("Text", ""),
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                        })

            return ToolResult.ok({
                "results": results,
                "query": query,
                "domain_filter": domain,
            })

        except requests.exceptions.RequestException as e:
            return ToolResult.error(ErrorCode.ERR_FETCH_FAILED, f"Network error: {str(e)}")
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _read_url_content(self, url: str) -> ToolResult:
        """Fetch URL and convert to Markdown."""
        # Validate protocol
        is_valid, error = self._validate_url_protocol(url)
        if not is_valid:
            return ToolResult.error(ErrorCode.ERR_INVALID_PROTOCOL, error)

        try:
            # Import requests and html2text locally
            import requests
        except ImportError:
            return ToolResult.error(
                ErrorCode.ERR_INVALID_INPUT,
                "requests library not available for URL fetching"
            )

        try:
            # Fetch URL
            response = requests.get(url, timeout=15, allow_redirects=True)

            # Check for successful status
            if response.status_code != 200:
                return ToolResult.error(
                    ErrorCode.ERR_FETCH_FAILED,
                    f"HTTP {response.status_code}: {response.reason}"
                )

            # Extract title from HTML head or use URL
            title = url
            if "<title>" in response.text:
                try:
                    start = response.text.index("<title>") + 7
                    end = response.text.index("</title>")
                    title = response.text[start:end].strip()
                except (ValueError, IndexError):
                    pass

            # Convert HTML to Markdown
            try:
                import html2text
                converter = html2text.HTML2Text()
                converter.ignore_links = False
                converter.body_width = 0
                content_markdown = converter.handle(response.text)
            except ImportError:
                # Fallback: if html2text not available, return plain text
                content_markdown = response.text[:5000]  # Limit to 5000 chars

            return ToolResult.ok({
                "status_code": response.status_code,
                "title": title,
                "content_markdown": content_markdown,
                "url": response.url,  # Final URL after redirects
            })

        except requests.exceptions.RequestException as e:
            return ToolResult.error(ErrorCode.ERR_FETCH_FAILED, f"Network error: {str(e)}")
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))
