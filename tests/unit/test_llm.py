"""
Unit Tests for LLM Management Layer (Track 5.2)
================================================
Tests LLMClient initialization, provider resolution, mock engine, and ReAct generation.
"""

import pytest
from orchestration.llm.client import LLMClient
from orchestration.llm.mock_engine import MockLLMEngine
from orchestration.llm.prompts import (
    REACT_AGENT_SYSTEM_PROMPT,
    CODER_AGENT_SYSTEM_PROMPT,
    RESEARCHER_AGENT_SYSTEM_PROMPT,
)


def test_mock_llm_engine_coding_simulation():
    engine = MockLLMEngine()
    messages = [
        {"role": "system", "content": "You are a coding agent"},
        {"role": "user", "content": "Write a python function to compute fibonacci"},
    ]
    step = engine.generate_step(messages, available_tools=["execute_python_code"])
    assert "Action: execute_python_code" in step
    assert "Action Input:" in step


def test_mock_llm_engine_research_simulation():
    engine = MockLLMEngine()
    messages = [
        {"role": "system", "content": "You are a researcher"},
        {"role": "user", "content": "Search for latest AI news"},
    ]
    step = engine.generate_step(messages, available_tools=["web_search"])
    assert "Action: web_search" in step


def test_mock_llm_engine_observation_convergence():
    engine = MockLLMEngine()
    messages = [
        {"role": "system", "content": "You are an agent"},
        {"role": "user", "content": "Calculate 5 + 5"},
        {"role": "user", "content": "Observation: Result: 10"},
    ]
    step = engine.generate_step(messages, available_tools=["calculate"], iteration=1)
    assert "Final Answer:" in step
    assert "10" in step


def test_llm_client_initialization():
    client = LLMClient(provider="mock")
    assert client.provider == "mock"
    assert client.temperature == 0.2

    response = client.generate(
        messages=[{"role": "user", "content": "Hello"}],
        available_tools=[],
    )
    assert response is not None
