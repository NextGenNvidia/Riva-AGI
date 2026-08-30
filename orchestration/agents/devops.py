import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

from orchestration.tools import tool_registry

@registry.register("devops", AgentCapabilities(description="Handles deployment, infrastructure, Docker, and terminal commands.", tools=["execute_command", "get_system_info", "read_file", "write_file", "list_directory"], agent_level="TASK_DOER"))
def devops_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to DevOps Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("WORKER_8")
    devops_tools = tool_registry.get_tools_by_names(["execute_command", "get_system_info", "read_file", "write_file", "list_directory"])
    
    sys_prompt = (
        "You are the expert DevOps Agent in an AGI system. "
        "You have tools to execute shell commands, inspect system info, and create/read configuration and deployment files (Docker, Kubernetes, CI/CD, scripts). "
        "When requested, execute commands safely and write deployment configs."
    )
    
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="devops",
        tools=devops_tools,
        return_tool_calls=True
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="devops",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value, "tools_count": len(tool_calls)}
    )
