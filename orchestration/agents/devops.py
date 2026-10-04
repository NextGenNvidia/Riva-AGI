import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

DEVOPS_TOOLS = ["execute_command", "get_system_info", "read_file", "write_file", "edit_file", "list_directory"]


@registry.register("devops", AgentCapabilities(description="Handles deployment, system administration, and infrastructure commands.", tools=DEVOPS_TOOLS, agent_level="TASK_DOER"))
def devops_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to DevOps Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("WORKER_8")
    sys_prompt = (
        "You are the DevOps Agent in the Riva-AGI autonomous system.\n"
        "You have access to system execution and environment tools: execute_command, get_system_info, read_file, write_file, edit_file, and list_directory.\n"
        "Execute system operations safely and inspect outputs and exit codes."
    )
    
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="devops",
        tools=DEVOPS_TOOLS,
        return_tool_calls=True
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="devops",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
