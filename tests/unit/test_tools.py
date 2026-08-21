"""
Unit Tests for Tool Calling Framework (Task O2)
================================================
Tests @tool decorator, ToolRegistry, ToolExecutor, Builtin Tools, and MCP Adapter.
"""

import os
import tempfile
from pathlib import Path
import pytest

from orchestration.orchestrator.schemas.tool import ToolCall, ToolResult
from orchestration.tools.base import ToolDefinition, tool
from orchestration.tools.executor import ToolExecutor, tool_executor
from orchestration.tools.mcp_adapter import MCPAdapter
from orchestration.tools.registry import ToolRegistry, tool_registry
from orchestration.tools.builtin.code_tools import check_python_syntax, execute_python_code
from orchestration.tools.builtin.file_tools import file_exists, list_directory, read_file, write_file
from orchestration.tools.builtin.system_tools import calculate, get_current_time, get_system_info
from orchestration.tools.builtin.web_tools import fetch_webpage, web_search


def test_tool_decorator_creates_tool_definition():
    @tool(name="custom_math_tool", description="Multiplies two numbers", category="math")
    def multiply(a: int, b: int) -> int:
        """Multiply a and b."""
        return a * b

    assert isinstance(multiply, ToolDefinition)
    assert multiply.name == "custom_math_tool"
    assert multiply.description == "Multiplies two numbers"
    assert multiply.category == "math"
    assert len(multiply.parameters) == 2
    assert multiply.parameters[0].name == "a"
    assert multiply.parameters[1].name == "b"

    # Test execution via callable
    func = multiply.get_callable()
    assert func(3, 4) == 12


def test_tool_schema_export():
    @tool(name="demo_tool", description="A demo tool")
    def sample_func(text: str, count: int = 1) -> str:
        return text * count

    openai_schema = sample_func.to_openai_schema()
    assert openai_schema["type"] == "function"
    assert openai_schema["function"]["name"] == "demo_tool"
    assert "text" in openai_schema["function"]["parameters"]["properties"]

    mcp_schema = sample_func.to_mcp_schema()
    assert mcp_schema["name"] == "demo_tool"
    assert "inputSchema" in mcp_schema


def test_tool_registry():
    registry = ToolRegistry()

    @tool(name="reg_tool_1", description="Tool 1", category="custom")
    def tool_1():
        return "1"

    registry.register(tool_1)
    assert registry.get("reg_tool_1") is not None
    assert len(registry.list_tools(category="custom")) == 1
    assert "reg_tool_1" in registry.get_tool_names()


def test_tool_executor_success_and_error():
    executor = ToolExecutor()

    # Success case
    call = ToolCall(
        call_id="call-001",
        tool_name="calculate",
        parameters={"expression": "10 * 5 + 2"},
        expected_return_type="str",
    )
    result = executor.execute(call)
    assert result.success is True
    assert "52" in str(result.output)
    assert result.execution_time_ms is not None

    # Unregistered tool case
    bad_call = ToolCall(
        call_id="call-002",
        tool_name="non_existent_tool_xyz",
        parameters={},
        expected_return_type="str",
    )
    bad_result = executor.execute(bad_call)
    assert bad_result.success is False
    assert "not registered" in bad_result.error


def test_file_tools():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "sample.txt"
        
        # Write
        w_res = write_file(str(test_file), "Hello Riva AGI")
        assert "Successfully wrote" in w_res

        # Check existence
        assert "Yes" in file_exists(str(test_file))

        # Read
        content = read_file(str(test_file))
        assert content == "Hello Riva AGI"

        # List
        ls_res = list_directory(tmpdir)
        assert "sample.txt" in ls_res


def test_code_tools():
    # Syntax check pass
    valid_code = "def add(x, y):\n    return x + y\nprint(add(2, 3))"
    assert "PASSED" in check_python_syntax(valid_code)

    # Syntax check fail
    invalid_code = "def bad_syntax(:\n    pass"
    assert "Syntax Error" in check_python_syntax(invalid_code)

    # Execution
    exec_res = execute_python_code("print('Autonomous AI Code Execution')")
    assert "[Exit Code 0]" in exec_res
    assert "Autonomous AI Code Execution" in exec_res


def test_system_tools():
    time_str = get_current_time()
    assert "Current System Time:" in time_str

    sys_info = get_system_info()
    assert "Python Version:" in sys_info

    calc_res = calculate("2 ** 8")
    assert "256" in calc_res


def test_mcp_adapter():
    tools_list = MCPAdapter.get_tools_list_response()
    assert "tools" in tools_list
    assert len(tools_list["tools"]) > 0

    # Call tool via MCP JSON-RPC format
    mcp_req = {
        "id": "mcp-test-1",
        "method": "tools/call",
        "params": {
            "name": "calculate",
            "arguments": {"expression": "100 / 4"},
        },
    }
    mcp_resp = MCPAdapter.handle_mcp_call(mcp_req)
    assert mcp_resp["isError"] is False
    assert "25" in mcp_resp["content"][0]["text"]
