"""
Riva-AGI Tool Calling Framework (Task O2)
=========================================
Exports ToolDefinition, @tool decorator, ToolRegistry, ToolExecutor,
and standard MCP Adapter.
"""

from orchestration.tools.base import ToolDefinition, ToolParameter, tool
from orchestration.tools.registry import ToolRegistry, tool_registry
from orchestration.tools.executor import ToolExecutor, tool_executor
from orchestration.tools.mcp_adapter import MCPAdapter
import orchestration.tools.builtin  # auto-registers builtin tools

__all__ = [
    "ToolDefinition",
    "ToolParameter",
    "tool",
    "ToolRegistry",
    "tool_registry",
    "ToolExecutor",
    "tool_executor",
    "MCPAdapter",
]
