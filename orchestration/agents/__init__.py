"""
Riva-AGI Agents Package
=======================
Contains specialized autonomous agents:
- BaseAgent (core ReAct & reflection engine)
- Coder Agent (autonomous software engineering)
- Researcher Agent (web & institutional research)
"""

from orchestration.agents.base import BaseAgent
from orchestration.agents.coder import coder_agent, coder_instance
from orchestration.agents.researcher import researcher_agent, researcher_instance

__all__ = [
    "BaseAgent",
    "coder_agent",
    "coder_instance",
    "researcher_agent",
    "researcher_instance",
]
