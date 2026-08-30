import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)


from orchestration.tools import tool_registry

@registry.register("researcher", AgentCapabilities(description="Handles internet research and data gathering.", tools=["web_search", "fetch_url_content", "read_file"], agent_level="TASK_DOER"))
def researcher_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Researcher Agent")
    
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("RESEARCHER")
    researcher_tools = tool_registry.get_tools_by_names(["web_search", "fetch_url_content", "read_file"])
    
    sys_prompt = (
        "You are the expert Researcher Agent in an AGI system. "
        "You have access to live web search (`web_search`) and webpage fetching (`fetch_url_content`) tools. "
        "Use `web_search` to query the web. Once you obtain search results, synthesize the findings and write a detailed, high-quality, structured summary answering the user's request with references."
    )
    
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="researcher",
        tools=researcher_tools,
        return_tool_calls=True
    )
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="researcher",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value, "tools_count": len(tool_calls)}
    )