"""
Autonomous Coder Agent — orchestration/agents/coder.py
======================================================
Autonomous software engineer for Riva-AGI. Capable of analyzing requirements,
generating Python code, running tests, self-debugging runtime/syntax errors,
and managing project files.
"""

import logging
from orchestration.agents.base import BaseAgent
from orchestration.llm.prompts import CODER_AGENT_SYSTEM_PROMPT
from orchestration.orchestrator.registry import AgentCapabilities, registry
from orchestration.orchestrator.schemas.input import InputData
from orchestration.orchestrator.schemas.response import AgentResponse

logger = logging.getLogger(__name__)

# Authorized tool suite for Coder Agent
CODER_TOOLS = [
    "execute_python_code",
    "check_python_syntax",
    "run_pytest",
    "read_file",
    "write_file",
    "list_directory",
    "file_exists",
]

# Instantiate core autonomous agent instance
coder_instance = BaseAgent(
    agent_id="coder",
    description="Autonomous software engineer capable of writing, testing, debugging, and running Python code.",
    system_prompt=CODER_AGENT_SYSTEM_PROMPT,
    tool_names=CODER_TOOLS,
)


@registry.register(
    "coder",
    AgentCapabilities(
        description="Handles autonomous software development, script execution, unit testing, and code self-debugging.",
        tools=CODER_TOOLS,
    ),
)
def coder_agent(task_data: InputData) -> AgentResponse:
    """
    Standard entrypoint called by the Root Orchestrator.
    Executes the autonomous ReAct coding loop.
    """
    logger.info("Executing Autonomous Coder Agent")
    return coder_instance.run(task_data)