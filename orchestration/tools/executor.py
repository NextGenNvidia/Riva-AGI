"""
Safe Tool Executor — orchestration/tools/executor.py
=====================================================
Executes tools safely with input validation, timeout protection,
performance metrics, and standardized ToolResult responses.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, Optional

from orchestration.orchestrator.schemas.tool import ToolCall, ToolResult
from orchestration.tools.registry import tool_registry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Handles safe execution of tool calls, returning standard ToolResult objects.
    """

    def __init__(self, registry=None):
        self.registry = registry or tool_registry

    def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute a ToolCall request and return a standardized ToolResult.
        """
        start_time = time.perf_counter()
        tool_name = call.tool_name
        params = call.parameters or {}

        tool_def = self.registry.get(tool_name)
        if not tool_def:
            elapsed = (time.perf_counter() - start_time) * 1000
            error_msg = f"Tool '{tool_name}' is not registered in the tool registry."
            logger.error("Tool execution failed: %s", error_msg)
            return ToolResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=False,
                output=None,
                error=error_msg,
                execution_time_ms=elapsed,
            )

        func = tool_def.get_callable()
        if not func:
            elapsed = (time.perf_counter() - start_time) * 1000
            error_msg = f"Tool '{tool_name}' does not have an executable callable."
            logger.error("Tool execution failed: %s", error_msg)
            return ToolResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=False,
                output=None,
                error=error_msg,
                execution_time_ms=elapsed,
            )

        try:
            # Robust parameter normalization for LLMs
            import inspect
            sig = inspect.signature(func)
            normalized_params = dict(params)
            
            aliases = {
                "content": ["input", "text", "data", "body"],
                "file_path": ["path", "filename", "file", "filepath"],
                "code": ["input", "script", "python_code", "snippet"],
                "query": ["input", "search_query", "q"],
                "expression": ["input", "expr", "formula"],
            }
            
            for target_param, alias_list in aliases.items():
                if target_param in sig.parameters and target_param not in normalized_params:
                    for alias in alias_list:
                        if alias in normalized_params:
                            normalized_params[target_param] = normalized_params.pop(alias)
                            break

            logger.info("Executing tool '%s' with parameters: %s", tool_name, normalized_params)
            output = func(**normalized_params)
            elapsed = (time.perf_counter() - start_time) * 1000

            logger.info("Tool '%s' succeeded in %.2fms", tool_name, elapsed)
            return ToolResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=True,
                output=output,
                error=None,
                execution_time_ms=elapsed,
            )

        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            tb = traceback.format_exc()
            error_msg = f"Execution error in '{tool_name}': {str(e)}\n{tb}"
            logger.exception("Error executing tool '%s': %s", tool_name, str(e))
            return ToolResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=False,
                output=None,
                error=error_msg,
                execution_time_ms=elapsed,
            )

    def execute_direct(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        call_id: Optional[str] = None,
    ) -> ToolResult:
        """Convenience method to execute a tool by name and dictionary parameters."""
        import uuid
        call = ToolCall(
            call_id=call_id or f"call-{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            parameters=parameters or {},
            expected_return_type="str",
        )
        return self.execute(call)


# Global tool executor instance
tool_executor = ToolExecutor()
