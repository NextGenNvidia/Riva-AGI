"""Unit tests for Gemini Live Function Calling Tools & Registry."""

from unittest.mock import MagicMock, patch
import pytest
from voice_speech.engine.gemini.tools import (
    dispatch_tool_call,
    fetch_news_summary,
    TOOL_REGISTRY,
    NEWS_TOOL_DECLARATION,
)


def test_tool_declaration():
    assert NEWS_TOOL_DECLARATION.name == "get_latest_news"
    assert "query" in NEWS_TOOL_DECLARATION.parameters.properties
    assert "query" in NEWS_TOOL_DECLARATION.parameters.required


@pytest.mark.anyio
async def test_dispatch_registered_tool():
    with patch("voice_speech.engine.gemini.tools.fetch_news_summary") as mock_fetch:
        mock_fetch.return_value = "Mocked Headline 1 | Mocked Headline 2"
        result = await dispatch_tool_call("get_latest_news", {"query": "artificial intelligence"})
        assert result == "Mocked Headline 1 | Mocked Headline 2"
        mock_fetch.assert_called_once_with("artificial intelligence")


@pytest.mark.anyio
async def test_fetch_news_summary_rss_mock():
    sample_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
        <item><title>AI Breakthrough Announced - TechNews</title></item>
        <item><title>Global Summit Begins - WorldNews</title></item>
    </channel></rss>"""

    mock_resp = MagicMock()
    mock_resp.read.return_value = sample_rss
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        summary = await fetch_news_summary("tech")
        assert "AI Breakthrough Announced" in summary
        assert "Global Summit Begins" in summary


@pytest.mark.anyio
async def test_dispatch_unsupported_tool():
    result = await dispatch_tool_call("non_existent_tool", {})
    assert "not supported" in result


@pytest.mark.anyio
async def test_custom_tool_registration():
    async def sample_handler(args):
        return f"Echo: {args.get('text', '')}"

    TOOL_REGISTRY["test_echo"] = sample_handler
    try:
        result = await dispatch_tool_call("test_echo", {"text": "hello"})
        assert result == "Echo: hello"
    finally:
        TOOL_REGISTRY.pop("test_echo", None)
