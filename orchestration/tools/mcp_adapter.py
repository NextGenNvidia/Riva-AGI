"""
Model Context Protocol (MCP) Adapter — orchestration/tools/mcp_adapter.py
==========================================================================
Provides standard MCP (Model Context Protocol) tool schema conversion,
JSON-RPC tool call formatting, and dynamic MCP server bridge capability.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from orchestration.orchestrator.schemas.tool import ToolCall, ToolResult
from orchestration.tools.base import ToolDefinition
from orchestration.tools.executor import tool_executor
from orchestration.tools.registry import tool_registry

logger = logging.getLogger(__name__)


class MCPAdapter:
    """
    Adapter layer to bridge Riva-AGI tools with standard MCP servers and clients.
    """

    @staticmethod
    def get_tools_list_response() -> Dict[str, Any]:
        """
        Generates standard MCP `tools/list` response object.
        """
        tools = tool_registry.list_tools()
        return {
            "tools": [t.to_mcp_schema() for t in tools]
        }

    @staticmethod
    def handle_mcp_call(request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming MCP `tools/call` JSON-RPC message.
        Example request:
        {
            "method": "tools/call",
            "params": {
                "name": "execute_python_code",
                "arguments": {"code": "print('hello')"}
            }
        }
        """
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        call_id = request.get("id", "mcp-call-001")

        if not tool_name:
            return {
                "isError": True,
                "content": [{"type": "text", "text": "Missing tool name in MCP request"}],
            }

        tool_call = ToolCall(
            call_id=str(call_id),
            tool_name=tool_name,
            parameters=arguments,
            expected_return_type="str",
        )

        result: ToolResult = tool_executor.execute(tool_call)

        return {
            "content": [
                {
                    "type": "text",
                    "text": str(result.output) if result.success else f"Error: {result.error}",
                }
            ],
            "isError": not result.success,
            "_metadata": {
                "execution_time_ms": result.execution_time_ms,
                "tool_name": result.tool_name,
            },
        }
