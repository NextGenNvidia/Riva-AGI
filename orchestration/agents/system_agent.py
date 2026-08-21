"""
System Agent — orchestration/agents/system_agent.py
===================================================
A real-time agent that can calculate dates, times, math, and system info.
"""
import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.agents.base import BaseAgent
from orchestration.llm.prompts import REACT_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Specialized System Prompt
SYSTEM_AGENT_PROMPT = REACT_AGENT_SYSTEM_PROMPT + """
You are Riva-System, the real-time system and utility agent for RIVA.
Your job is to answer questions about the current date, time, basic math, or system status using your tools.
Always use tools to check the real date/time instead of hallucinating.
"""

@registry.register(
    name="system",
    capabilities=AgentCapabilities(
        description="Handles real-time queries for date, time, system status, and mathematical calculations.",
        tools=["get_current_time", "calculate", "get_system_info"]
    )
)
def system_agent_handler(task_data: InputData) -> AgentResponse:
    """Entry point for the System Agent."""
    logger.info("Executing System Agent")
    
    agent = BaseAgent(
        agent_id="system",
        description="Handles real-time date, time, and system queries.",
        system_prompt=SYSTEM_AGENT_PROMPT,
        tool_names=["get_current_time", "calculate", "get_system_info"],
        max_iterations=5
    )
    
    start_time = time.time()
    return agent.run(task_data)
