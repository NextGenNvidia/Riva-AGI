"""
Autonomous Researcher Agent — orchestration/agents/researcher.py
=================================================================
Autonomous research and information retrieval agent for Riva-AGI.
Capable of web queries, extracting webpage text, analyzing institutional data,
and synthesizing structured research summaries.
"""

import logging
from orchestration.agents.base import BaseAgent
from orchestration.llm.prompts import RESEARCHER_AGENT_SYSTEM_PROMPT
from orchestration.orchestrator.registry import AgentCapabilities, registry
from orchestration.orchestrator.schemas.input import InputData
from orchestration.orchestrator.schemas.response import AgentResponse

logger = logging.getLogger(__name__)

# Authorized tool suite for Researcher Agent
RESEARCHER_TOOLS = [
    "web_search",
    "fetch_webpage",
    "read_file",
    "get_current_time",
    "calculate",
]

# Instantiate core autonomous agent instance
researcher_instance = BaseAgent(
    agent_id="researcher",
    description="Autonomous researcher capable of live web queries, webpage reading, and multi-source data synthesis.",
    system_prompt=RESEARCHER_AGENT_SYSTEM_PROMPT,
    tool_names=RESEARCHER_TOOLS,
)


@registry.register(
    "researcher",
    AgentCapabilities(
        description="Handles live web research, information retrieval, webpage reading, and fact synthesis.",
        tools=RESEARCHER_TOOLS,
    ),
)
def researcher_agent(task_data: InputData) -> AgentResponse:
    """
    Standard entrypoint called by the Root Orchestrator.
    Executes the autonomous ReAct research loop.
    """
    logger.info("Executing Autonomous Researcher Agent")
    return researcher_instance.run(task_data)