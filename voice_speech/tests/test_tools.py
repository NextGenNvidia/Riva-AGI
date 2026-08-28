"""Unit tests for Gemini Live Function Calling Tools & Registry."""

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
    result = await dispatch_tool_call("get_latest_news", {"query": "artificial intelligence"})
    assert isinstance(result, str)
    assert len(result) > 0


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
