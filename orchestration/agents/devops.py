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
    import platform
    current_os = platform.system()
    sys_prompt = (
        f"You are the DevOps Agent in the Riva-AGI autonomous system.\n"
        f"Host Operating System: {current_os} (Shell: {'PowerShell/cmd.exe' if current_os == 'Windows' else 'bash/sh'}).\n"
        "You have direct access to system execution tools: execute_command, get_system_info, read_file, write_file, edit_file, list_directory.\n"
        "When launching applications, browsers, or URLs on Windows, use 'start <app_or_url>' (e.g. 'start chrome', 'start https://youtube.com', 'start notepad').\n"
        "Do NOT guess Linux-only commands like 'which', 'open', or 'google-chrome' on Windows.\n"
        "Execute commands directly in 1 turn without unnecessary exploratory commands."
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
