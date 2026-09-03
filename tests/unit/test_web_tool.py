"""Tests for LAEW WebTool (CONTRACT.md)."""

import pytest

from laew.tools.base import ErrorCode
from laew.tools.web import WebTool


@pytest.fixture
def tool():
    """Create WebTool instance."""
    return WebTool()


# === Protocol validation ===

def test_invalid_protocol_ftp(tool):
    """Test that ftp:// protocol is blocked."""
    result = tool.read_url_content("ftp://example.com/file.txt")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_PROTOCOL


def test_invalid_protocol_file(tool):
    """Test that file:// protocol is blocked."""
    result = tool.read_url_content("file:///etc/passwd")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_PROTOCOL


def test_invalid_protocol_custom(tool):
    """Test that custom protocols are blocked."""
    result = tool.read_url_content("custom://example.com")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_PROTOCOL


def test_valid_protocol_http(tool):
    """Test that http:// protocol is accepted (will fail on fetch, but not protocol check)."""
    result = tool.read_url_content("http://example.com")

    # This will fail on network fetch, not protocol validation
    # So we check that it's not a protocol error
    if not result.success:
        assert result.error_code != ErrorCode.ERR_INVALID_PROTOCOL


def test_valid_protocol_https(tool):
    """Test that https:// protocol is accepted (will fail on fetch, but not protocol check)."""
    result = tool.read_url_content("https://example.com")

    # This will fail on network fetch, not protocol validation
    if not result.success:
        assert result.error_code != ErrorCode.ERR_INVALID_PROTOCOL


# === URL validation ===

def test_invalid_url_no_domain(tool):
    """Test that URL without domain is rejected."""
    result = tool.read_url_content("https://")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_PROTOCOL


def test_invalid_url_malformed(tool):
    """Test that malformed URL is rejected."""
    result = tool.read_url_content("not a url")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_PROTOCOL


# === Search validation ===

def test_search_web_requires_query(tool):
    """Test that search_web requires a query parameter."""
    result = tool.search_web("")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_INPUT


def test_search_web_query_must_be_string(tool):
    """Test that search_web query must be a string."""
    result = tool.search_web(None)

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_INPUT


# === Operation validation ===

def test_validate_search_web_operation(tool):
    """Test that search_web operation is recognized."""
    valid, error = tool.validate("search_web", query="test")

    assert valid
    assert error is None


def test_validate_read_url_content_operation(tool):
    """Test that read_url_content operation is recognized."""
    valid, error = tool.validate("read_url_content", url="https://example.com")

    assert valid
    assert error is None


def test_validate_unknown_operation(tool):
    """Test that unknown operations are rejected."""
    valid, error = tool.validate("unknown_op")

    assert not valid
    assert error is not None


# === Integration tests ===

def test_search_web_no_network_error(tool):
    """Test that search_web handles network errors gracefully."""
    # This test will depend on network availability
    # If network is unavailable, it should return ERR_FETCH_FAILED
    result = tool.search_web("python documentation")

    # Check that we get either success or a proper error code
    if not result.success:
        assert result.error_code in {ErrorCode.ERR_FETCH_FAILED, ErrorCode.ERR_INVALID_INPUT}
    else:
        # On success, should have results
        assert "results" in result.data
        assert isinstance(result.data["results"], list)


def test_read_url_content_with_domain_filter(tool):
    """Test search_web with domain filter."""
    result = tool.search_web("rust documentation", domain="docs.rs")

    # Check that we get either success or a proper error code
    if not result.success:
        assert result.error_code in {ErrorCode.ERR_FETCH_FAILED, ErrorCode.ERR_INVALID_INPUT}
    else:
        assert result.data.get("domain_filter") == "docs.rs"


# === Read-only enforcement ===

def test_tool_does_not_require_approval(tool):
    """Test that web tool operations don't require approval."""
    # Web tool is always read-only, so approval should never be needed
    assert not tool._requires_approval
