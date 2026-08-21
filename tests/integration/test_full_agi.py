"""
End-to-End Integration Tests for Riva-AGI
==========================================
Validates that the Root Orchestrator routes to intelligent Coder and Researcher
agents, tools execute seamlessly, and structured AgentResponses are returned.
"""

import pytest
from orchestration.agents.coder import coder_agent
from orchestration.agents.researcher import researcher_agent
from orchestration.orchestrator.main import run_orchestrator
from orchestration.orchestrator.schemas.input import InputData, InputType
from orchestration.orchestrator.schemas.response import ResponseStatus


def test_coder_agent_standalone_execution():
    payload = InputData(
        input_type=InputType.TEXT,
        text_content="Write and execute a Python function to compute fibonacci numbers",
    )
    response = coder_agent(payload)

    assert response.agent_id == "coder"
    assert response.status == ResponseStatus.SUCCESS
    assert len(response.tool_calls) > 0
    assert response.tool_calls[0].tool_name in ["execute_python_code", "write_file", "check_python_syntax"]
    assert response.content is not None


def test_researcher_agent_standalone_execution():
    payload = InputData(
        input_type=InputType.TEXT,
        text_content="Search and research the history of autonomous AI agents",
    )
    response = researcher_agent(payload)

    assert response.agent_id == "researcher"
    assert response.status == ResponseStatus.SUCCESS
    assert len(response.tool_calls) > 0
    assert response.tool_calls[0].tool_name == "web_search"
    assert response.content is not None


def test_orchestrator_routes_to_coder_and_executes():
    result = run_orchestrator("Write a Python script to calculate prime numbers")

    assert result["agent"] == "coder"
    assert result["intent"] == "coding"
    assert result["response_payload"] is not None
    assert result["response_payload"].status == ResponseStatus.SUCCESS


def test_orchestrator_routes_to_researcher_and_executes():
    result = run_orchestrator("Research latest advances in multi-agent orchestration")

    assert result["agent"] == "researcher"
    assert result["intent"] == "research"
    assert result["response_payload"] is not None
    assert result["response_payload"].status == ResponseStatus.SUCCESS
