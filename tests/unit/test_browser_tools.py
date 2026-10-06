"""
Unit tests for Browser Tools in Orchestration Tool Registry
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from orchestration.tools.registry import tool_registry
from orchestration.tools.builtin.browser_tools import (
    inspect_browser_dom,
    stream_code_to_editor,
    run_browser_code,
    submit_browser_code,
    navigate_browser,
)


def test_browser_tools_registered_in_tool_registry():
    tools = tool_registry.get_all_tools()
    
    expected_tools = [
        "inspect_browser_dom",
        "stream_code_to_editor",
        "run_browser_code",
        "submit_browser_code",
        "navigate_browser",
    ]
    for tool_name in expected_tools:
        assert tool_name in tools, f"Tool {tool_name} was not registered in tool_registry"
        defn = tool_registry.get_tool_definition(tool_name)
        assert defn is not None
        assert defn.category == "browser"


def test_stream_code_to_editor_empty_code():
    res_str = stream_code_to_editor(code="")
    res = json.loads(res_str)
    assert "error" in res
    assert "No code" in res["error"]


@patch("orchestration.tools.builtin.browser_tools._get_cdp_browser")
def test_inspect_browser_dom_no_browser(mock_get_cdp):
    mock_get_cdp.return_value = None
    res_str = inspect_browser_dom(target="active")
    res = json.loads(res_str)
    assert "error" in res
