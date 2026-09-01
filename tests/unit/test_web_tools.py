import io
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from orchestration.tools.builtin.web_tools import (
    web_search,
    fetch_url_content,
    _clean_html_text,
    _extract_ddg_url,
)
from orchestration.tools.registry import tool_registry


def test_web_tools_registered():
    """Verify that web tools are registered in tool_registry."""
    assert tool_registry.get_tool("web_search") is not None
    assert tool_registry.get_tool("fetch_url_content") is not None

    search_def = tool_registry.get_tool_definition("web_search")
    assert search_def.category == "web"
    assert "query" in search_def.parameters_schema

    fetch_def = tool_registry.get_tool_definition("fetch_url_content")
    assert fetch_def.category == "web"
    assert "url" in fetch_def.parameters_schema


def test_clean_html_text():
    """Test HTML stripping, style removal, and entity decoding."""
    raw = """
    <html>
        <head>
            <style>body { color: red; }</style>
            <script>alert('malicious');</script>
        </head>
        <body>
            <!-- Comment here -->
            <h1>Hello &amp; Welcome!</h1>
            <p>This is a <b>test</b> of HTML cleaning.</p>
        </body>
    </html>
    """
    cleaned = _clean_html_text(raw)
    assert "body { color: red; }" not in cleaned
    assert "alert('malicious')" not in cleaned
    assert "<!-- Comment here -->" not in cleaned
    assert "Hello & Welcome!" in cleaned
    assert "This is a test of HTML cleaning." in cleaned


def test_extract_ddg_url():
    """Test extracting destination URL from DuckDuckGo redirect link."""
    ddg_redirect = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2Fdoc%2F&rut=123"
    assert _extract_ddg_url(ddg_redirect) == "https://www.python.org/doc/"

    direct_url = "https://example.com/about"
    assert _extract_ddg_url(direct_url) == "https://example.com/about"


def test_web_search_empty():
    """Test web_search with empty query."""
    result = web_search("   ")
    assert "Error: Search query cannot be empty." in result


def test_web_search_success_mock():
    """Test web_search with mocked DuckDuckGo HTML response."""
    mock_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <div class="result results_links results_links_deep web-result">
            <div class="result__body links_main">
                <h2 class="result__title">
                    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F">Python Programming</a>
                </h2>
                <a class="result__snippet" href="#">Python is a high-level general-purpose programming language.</a>
            </div>
        </div>
        <div class="result results_links results_links_deep web-result">
            <div class="result__body links_main">
                <h2 class="result__title">
                    <a class="result__a" href="https://docs.python.org/3/">Python 3 Documentation</a>
                </h2>
                <a class="result__snippet" href="#">Official documentation for Python 3.</a>
            </div>
        </div>
    </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.read.return_value = mock_html.encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = web_search("python tutorial", max_results=2)
        assert "1. **Title**: Python Programming" in result
        assert "**URL**: https://www.python.org/" in result
        assert "**Snippet**: Python is a high-level" in result
        assert "2. **Title**: Python 3 Documentation" in result
        assert "**URL**: https://docs.python.org/3/" in result


def test_web_search_no_results():
    """Test web_search when HTML contains no result links."""
    mock_response = MagicMock()
    mock_response.read.return_value = b"<html><body><div>No results found</div></body></html>"
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = web_search("xyznonexistentquery12345")
        assert "No search results found for query: 'xyznonexistentquery12345'." in result


def test_web_search_network_error():
    """Test web_search error handling when network request fails."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        result = web_search("error query")
        assert "Error performing web search: <urlopen error Connection refused>" in result


def test_fetch_url_content_empty():
    """Test fetch_url_content with empty url."""
    result = fetch_url_content("")
    assert "Error: URL cannot be empty." in result


def test_fetch_url_content_success_mock():
    """Test fetch_url_content strips HTML and extracts plain text."""
    mock_html = """
    <!DOCTYPE html>
    <html>
        <head><title>Test Page</title><style>p { margin: 0; }</style></head>
        <body>
            <h1>Welcome to Riva-AGI</h1>
            <p>Riva-AGI is an advanced agentic intelligence framework.</p>
            <script>console.log('test');</script>
        </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.read.return_value = mock_html.encode("utf-8")
    mock_response.headers.get.return_value = "text/html; charset=utf-8"
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = fetch_url_content("https://example.com/page")
        assert "Welcome to Riva-AGI" in result
        assert "Riva-AGI is an advanced agentic intelligence framework." in result
        assert "console.log" not in result
        assert "p { margin: 0; }" not in result


def test_fetch_url_content_truncation():
    """Test fetch_url_content truncates long content properly."""
    long_content = "<p>" + ("A" * 5000) + "</p>"
    mock_response = MagicMock()
    mock_response.read.return_value = long_content.encode("utf-8")
    mock_response.headers.get.return_value = "text/html"
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = fetch_url_content("https://example.com/long", max_chars=100)
        assert len(result) > 100
        assert "... [Content truncated]" in result
        assert result.startswith("A" * 100)


def test_fetch_url_content_error():
    """Test fetch_url_content error handling."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="https://example.com/404", code=404, msg="Not Found", hdrs={}, fp=io.BytesIO()
    )):
        result = fetch_url_content("https://example.com/404")
        assert "Error fetching URL content: HTTP Error 404: Not Found" in result
