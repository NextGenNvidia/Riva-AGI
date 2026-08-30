import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

from orchestration.tools import tool_registry

@registry.register("qa_tester", AgentCapabilities(description="Runs quality assurance tests, pytest execution, and edge case validations.", tools=["execute_command", "read_file", "write_file"], agent_level="TASK_DOER"))
def qa_tester_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to QA Tester Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("WORKER_6")
    qa_tools = tool_registry.get_tools_by_names(["execute_command", "read_file", "write_file"])
    
    sys_prompt = (
        "You are the expert QA Tester Agent in an AGI system. "
        "You have tools to write test suites and execute tests (e.g., pytest, unittest, linters) using execute_command. "
        "When writing test cases, create proper test files and verify their execution."
    )
    
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="qa_tester",
        tools=qa_tools,
        return_tool_calls=True
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="qa_tester",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value, "tools_count": len(tool_calls)}
    )
