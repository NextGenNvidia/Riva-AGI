"""Dummy System Agent — orchestration/agents/dummy_system_agent.py
=================================================================
A 3rd dummy agent to test the Registration System (Task O4).
Includes a simulated orchestrator router to satisfy the O1 dependency check.
"""
import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

# Setup standard logger
logger = logging.getLogger(__name__)

@registry.register(
    name="dummy_system",
    capabilities=AgentCapabilities(
        description="Handles system-level operations like reading files or checking memory.",
        tools=["list_directory", "read_file"],
        agent_level="TASK_DOER"
    )
)
def dummy_system_agent(task_data: InputData) -> AgentResponse:
    """
    Executes a system level task.
    Takes <10 lines to add to the system!
    """
    logger.info(f"[Dummy System Agent] Executing task: {task_data.text_content}")
    
    start_time = time.time()
    
    # Assign and fetch the API key dynamically based on its exact role
    my_key = key_manager.get_api_key_for_role("DUMMY_SYSTEM")
    # System instruction tailored for this agent
    sys_prompt = f"You are the dummy_system agent. Your job is to fulfill the user's request expertly."
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="dummy_system"
    )
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="dummy_system",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )

