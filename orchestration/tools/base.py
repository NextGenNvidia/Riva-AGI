"""
Tool Definition & Base Schema — orchestration/tools/base.py
=============================================================
Defines the core Tool abstraction, parameter validation schemas,
and the @tool decorator for converting Python functions into AI-callable tools.

This implements Task O2 (Shared Tool-Calling Schema) and supports MCP / Function Calling.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints
from pydantic import BaseModel, Field, ConfigDict, create_model

from orchestration.orchestrator.schemas.tool import ToolCall, ToolResult


class ToolParameter(BaseModel):
    """Schema for an individual parameter of a tool."""
    name: str = Field(..., description="Name of the parameter")
    type_name: str = Field(..., description="Python type name (e.g. str, int, bool, list)")
    description: str = Field(default="", description="Description of what this parameter does")
    required: bool = Field(default=True, description="Whether this parameter is required")
    default: Any = Field(default=None, description="Default value if parameter is optional")


class ToolDefinition(BaseModel):
    """
    Complete metadata definition for a tool available to Riva-AGI agents.
    """
    name: str = Field(..., description="Unique tool name (e.g. 'execute_python_code')")
    description: str = Field(..., description="Detailed description of tool capability and usage")
    category: str = Field(default="general", description="Category: file, code, web, system, institutional")
    parameters: List[ToolParameter] = Field(default_factory=list, description="List of accepted parameters")
    parameters_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for parameters")
    expected_return_type: str = Field(default="str", description="Expected return type (e.g. str, dict, list)")
    tags: List[str] = Field(default_factory=list, description="Searchable tags for tool discovery")
    
    # Store callable function reference (excluded from serialization)
    _func: Optional[Callable] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def set_callable(self, func: Callable) -> None:
        """Attach the Python function implementation."""
        self._func = func

    def get_callable(self) -> Optional[Callable]:
        """Retrieve the Python function implementation."""
        return self._func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow direct invocation of the tool like a standard Python function."""
        if self._func is None:
            raise ValueError(f"Tool '{self.name}' has no executable callable attached.")
        return self._func(*args, **kwargs)

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert tool metadata to standard OpenAI / Groq function calling format."""
        properties = {}
        required = []
        for param in self.parameters:
            prop_type = "string"
            if param.type_name in ["int", "float"]:
                prop_type = "number"
            elif param.type_name == "bool":
                prop_type = "boolean"
            elif param.type_name in ["list", "List"]:
                prop_type = "array"
            elif param.type_name in ["dict", "Dict"]:
                prop_type = "object"

            properties[param.name] = {
                "type": prop_type,
                "description": param.description or param.name,
            }
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_mcp_schema(self) -> Dict[str, Any]:
        """Convert tool metadata to Model Context Protocol (MCP) standard tool format."""
        openai_fmt = self.to_openai_schema()
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": openai_fmt["function"]["parameters"],
        }


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    tags: Optional[List[str]] = None,
    expected_return_type: Optional[str] = None,
) -> Callable[[Callable], ToolDefinition]:
    """
    Decorator to convert any standard Python function into a Riva-AGI ToolDefinition.
    
    Automatically parses:
    - Function name
    - Docstring -> Description
    - Type annotations -> Parameter schemas and expected_return_type
    """
    def decorator(func: Callable) -> ToolDefinition:
        tool_name = name or func.__name__
        tool_doc = description or inspect.getdoc(func) or f"Tool: {tool_name}"
        
        # Parse function signature and type hints
        sig = inspect.signature(func)
        type_hints = {}
        try:
            type_hints = get_type_hints(func)
        except Exception:
            pass

        parameters: List[ToolParameter] = []
        json_properties: Dict[str, Any] = {}
        required_params: List[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ["self", "cls"]:
                continue
            
            # Determine type
            param_type = type_hints.get(param_name, str)
            type_name = getattr(param_type, "__name__", str(param_type))
            is_required = param.default == inspect.Parameter.empty
            default_val = None if is_required else param.default

            parameters.append(
                ToolParameter(
                    name=param_name,
                    type_name=type_name,
                    description=f"Argument {param_name}",
                    required=is_required,
                    default=default_val,
                )
            )
            
            # Build JSON Schema property
            prop_type = "string"
            if type_name in ["int", "float"]:
                prop_type = "number"
            elif type_name == "bool":
                prop_type = "boolean"
            elif type_name in ["list", "List"]:
                prop_type = "array"
            elif type_name in ["dict", "Dict"]:
                prop_type = "object"

            json_properties[param_name] = {"type": prop_type}
            if is_required:
                required_params.append(param_name)

        return_hint = type_hints.get("return", str)
        ret_type = expected_return_type or getattr(return_hint, "__name__", str(return_hint))

        parameters_schema = {
            "type": "object",
            "properties": json_properties,
            "required": required_params,
        }

        tool_def = ToolDefinition(
            name=tool_name,
            description=tool_doc,
            category=category,
            parameters=parameters,
            parameters_schema=parameters_schema,
            expected_return_type=ret_type,
            tags=tags or [],
        )
        tool_def.set_callable(func)
        return tool_def

    return decorator
