"""
Tool Schemas — orchestrator/schemas/tool.py
============================================
Defines how agents REQUEST tool execution (ToolCall) and how the orchestrator
RETURNS execution results back to agents (ToolResult).

WHY THIS FILE EXISTS (Issue Fix #1 — Modular Package):
    Isolated from input and response schemas so the Agents/LLM team can iterate
    on tool-calling contracts without merge conflicts with other teams.

WHY ToolResult EXISTS (Issue Fix #2 — Missing Return Schema):
    The old schema only had ToolCall (agent → orchestrator request) but NO
    schema for how the orchestrator sends execution results BACK to the agent.
    ToolResult closes that gap and completes the bidirectional tool lifecycle:

        Agent  ──ToolCall--->  Orchestrator  ──executes--->  Tool
        Agent  <---ToolResult──  Orchestrator  <---output──  Tool
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


# ============================================================================
# TOOL CALL — Agent requests the orchestrator to execute a tool
# ============================================================================

class ToolCall(BaseModel):
    """
    Schema defining how an agent REQUESTS the orchestrator to execute a tool.

    Fields:
        call_id             — Unique ID to track this specific invocation across
                              async queues and logs.
        tool_name           — Name of the tool/function to execute.
        parameters          — Key-value arguments passed into the tool function.
        expected_return_type — Tells the orchestrator what data format to expect
                              back from the tool (e.g., "str", "dict", "json").

    Data flow:
        Agent  --->  ToolCall  --->  Root Orchestrator  --->  Tool Execution
    """
    call_id: str = Field(
        ...,
        description="Unique identifier tracking this specific tool invocation request."
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool function to call (e.g., 'web_search', 'calculate_sum')."
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value dictionary of arguments passed into the tool function."
    )
    expected_return_type: str = Field(
        ...,
        description="Expected data format returned by the tool (e.g., 'str', 'dict', 'image_url', 'json')."
    )


# ============================================================================
# TOOL RESULT — Orchestrator returns execution results back to the agent
# ============================================================================

class ToolResult(BaseModel):
    """
    Schema for how the orchestrator RETURNS tool execution results to the agent.

    This model closes the round-trip lifecycle:
        1. Agent sends ToolCall  →  Orchestrator executes the tool.
        2. Orchestrator wraps the output in ToolResult  →  sends back to Agent.

    Fields:
        call_id           — Must match the original ToolCall.call_id so the agent
                            can correlate request ↔ response.
        tool_name         — Echoed back for logging and debugging clarity.
        success           — True if the tool executed without errors, False otherwise.
        output            — The actual return value from the tool (can be any type).
        error             — Error message string if success is False, else None.
        execution_time_ms — How long the tool took to execute (in milliseconds).

    Data flow:
        Tool Execution  --->  ToolResult  --->  Root Orchestrator  --->  Agent
    """
    call_id: str = Field(
        ...,
        description="Must match the original ToolCall.call_id for request-response correlation."
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool that was executed (echoed for logging)."
    )
    success: bool = Field(
        ...,
        description="True if the tool ran successfully, False if it errored."
    )
    output: Any = Field(
        default=None,
        description="The actual return value from the tool execution (any JSON-serializable type)."
    )
    error: Optional[str] = Field(
        default=None,
        description="Error details if success is False, otherwise None."
    )
    execution_time_ms: Optional[float] = Field(
        default=None,
        description="How long the tool took to execute, in milliseconds."
    )
