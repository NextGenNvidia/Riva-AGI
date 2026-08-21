"""
Tool Registry — orchestration/tools/registry.py
================================================
Central registry for dynamic discovery, management, and retrieval of tools
across all agent categories in Riva-AGI.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Union
from orchestration.tools.base import ToolDefinition, tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for managing and discovering agent-executable tools.
    """

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool_or_func: Union[ToolDefinition, Callable]) -> ToolDefinition:
        """
        Register a ToolDefinition or a decorated Python function.
        """
        if isinstance(tool_or_func, ToolDefinition):
            tool_def = tool_or_func
        elif hasattr(tool_or_func, "name") and isinstance(tool_or_func, ToolDefinition):
            tool_def = tool_or_func
        elif callable(tool_or_func):
            tool_def = tool()(tool_or_func)
        else:
            raise TypeError(f"Cannot register {type(tool_or_func)} as a tool")

        self._tools[tool_def.name] = tool_def
        logger.debug("Registered tool '%s' (category: %s)", tool_def.name, tool_def.category)
        return tool_def

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Retrieve a tool definition by name."""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """List all registered tools, optionally filtered by category."""
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def get_tool_names(self) -> List[str]:
        """Get names of all registered tools."""
        return list(self._tools.keys())

    def get_openai_schemas(self, tool_names: Optional[List[str]] = None) -> List[Dict]:
        """
        Export registered tools to OpenAI / Groq tool definitions format.
        """
        tools = (
            [self._tools[name] for name in tool_names if name in self._tools]
            if tool_names
            else list(self._tools.values())
        )
        return [t.to_openai_schema() for t in tools]

    def get_mcp_schemas(self, tool_names: Optional[List[str]] = None) -> List[Dict]:
        """Export registered tools to Model Context Protocol (MCP) format."""
        tools = (
            [self._tools[name] for name in tool_names if name in self._tools]
            if tool_names
            else list(self._tools.values())
        )
        return [t.to_mcp_schema() for t in tools]


# Global tool registry singleton
tool_registry = ToolRegistry()
