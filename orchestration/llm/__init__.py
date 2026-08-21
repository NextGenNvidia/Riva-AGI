"""
LLM Management Layer for Riva-AGI
=================================
Exports LLMClient, prompt templates, and Mock engine.
"""

from orchestration.llm.client import LLMClient, llm_client
from orchestration.llm.mock_engine import MockLLMEngine, mock_llm_engine
from orchestration.llm.prompts import (
    REACT_AGENT_SYSTEM_PROMPT,
    CODER_AGENT_SYSTEM_PROMPT,
    RESEARCHER_AGENT_SYSTEM_PROMPT,
    REFLECTION_PROMPT,
)

__all__ = [
    "LLMClient",
    "llm_client",
    "MockLLMEngine",
    "mock_llm_engine",
    "REACT_AGENT_SYSTEM_PROMPT",
    "CODER_AGENT_SYSTEM_PROMPT",
    "RESEARCHER_AGENT_SYSTEM_PROMPT",
    "REFLECTION_PROMPT",
]
