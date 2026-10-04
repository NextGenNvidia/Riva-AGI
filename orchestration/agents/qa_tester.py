import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

QA_TOOLS = ["execute_command", "read_file", "write_file", "list_directory"]


@registry.register("qa_tester", AgentCapabilities(description="Runs quality assurance tests, analyzes test suites, and verifies bug fixes.", tools=QA_TOOLS, agent_level="TASK_DOER"))
def qa_tester_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to QA Tester Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("WORKER_6")
    sys_prompt = (
        "You are the QA Tester Agent in the Riva-AGI autonomous system.\n"
        "You have access to testing tools: execute_command, read_file, write_file, and list_directory.\n"
        "Run test frameworks (e.g. pytest, unittest), check coverage, and verify test assertions directly."
    )
    
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="qa_tester",
        tools=QA_TOOLS,
        return_tool_calls=True
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="qa_tester",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
