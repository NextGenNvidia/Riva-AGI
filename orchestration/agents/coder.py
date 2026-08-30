import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)


from orchestration.tools import tool_registry

@registry.register("coder", AgentCapabilities(description="Handles coding and software development tasks.", tools=["read_file", "write_file", "edit_file", "list_directory", "execute_command"], agent_level="TASK_DOER"))
def coder_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Coder Agent")
    
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("CODER")
    coder_tools = tool_registry.get_tools_by_names(["read_file", "write_file", "edit_file", "list_directory", "execute_command"])
    
    sys_prompt = (
        "You are the expert Coder Agent in an AGI system. "
        "You have direct access to tools for reading, writing, editing files, and running commands. "
        "When the user asks you to implement, create, or modify code, use write_file or edit_file to save the files to disk. "
        "Always write clean, production-ready, type-annotated code."
    )
    
    # Call the GenAI LLM with tools
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="coder",
        tools=coder_tools,
        return_tool_calls=True
    )
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="coder",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value, "tools_count": len(tool_calls)}
    )