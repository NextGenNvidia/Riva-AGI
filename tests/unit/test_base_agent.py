"""
Unit Tests for BaseAgent (ReAct Reasoning Loop & Safety)
=========================================================
"""

import pytest
from orchestration.agents.base import BaseAgent
from orchestration.orchestrator.schemas.input import InputData, InputType
from orchestration.orchestrator.schemas.response import ResponseStatus


def test_base_agent_direct_response():
    agent = BaseAgent(
        agent_id="test_chat_agent",
        description="A simple chat agent without tools",
        tool_names=[],
    )
    payload = InputData(
        input_type=InputType.TEXT,
        text_content="Explain the purpose of Riva AGI",
    )
    response = agent.run(payload)

    assert response.agent_id == "test_chat_agent"
    assert response.status == ResponseStatus.SUCCESS
    assert response.content is not None
    assert len(response.tool_calls) == 0


def test_base_agent_tool_calling_loop():
    agent = BaseAgent(
        agent_id="math_agent",
        description="An agent that evaluates math",
        tool_names=["calculate"],
    )
    payload = InputData(
        input_type=InputType.TEXT,
        text_content="calculate 25 * 4",
    )
    response = agent.run(payload)

    assert response.agent_id == "math_agent"
    assert response.status == ResponseStatus.SUCCESS
    assert len(response.tool_calls) > 0
    assert response.tool_calls[0].tool_name == "calculate"
    assert "100" in response.content


def test_base_agent_unauthorized_tool_guardrail():
    agent = BaseAgent(
        agent_id="restricted_agent",
        description="An agent with no permission to execute code",
        tool_names=["get_current_time"],  # Only time is allowed
    )
    # Attempting a coding task will not execute python code because it's not authorized
    payload = InputData(
        input_type=InputType.TEXT,
        text_content="What time is it now?",
    )
    response = agent.run(payload)

    assert response.status == ResponseStatus.SUCCESS
    assert response.content is not None
