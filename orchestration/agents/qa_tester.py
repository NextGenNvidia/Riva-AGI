import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

QA_TOOLS = [
    "execute_command",
    "read_file",
    "write_file",
    "list_directory",
    "inspect_browser_dom",
    "stream_code_to_editor",
    "run_browser_code",
    "submit_browser_code",
]


@registry.register("qa_tester", AgentCapabilities(description="Runs quality assurance tests, analyzes test suites, and verifies bug fixes.", tools=QA_TOOLS, agent_level="TASK_DOER"))
def qa_tester_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to QA Tester Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("QA_TESTER")
    sys_prompt = (
        "You are the Principal Quality Assurance Engineer (QA Tester Agent) in the Riva-AGI framework.\n"
        "Your mission is to design, write, execute, and verify automated test suites to ensure 100% functional integrity and regression safety.\n\n"
        "OPERATIONAL PROTOCOLS:\n"
        "1. Active Tool Execution: You have access to tools: execute_command, read_file, write_file, and list_directory. "
        "Directly inspect existing tests, write new test suites using pytest/unittest, and run test runners using execute_command.\n"
        "2. Comprehensive Coverage: Design tests covering happy paths, edge cases, boundary conditions, invalid inputs, and error/exception handling.\n"
        "3. Failure Diagnosis: When a test fails, analyze the stack trace and stderr, identify the precise breaking line, and articulate the fix clearly.\n"
        "4. Validation Standards: Ensure all test files follow naming conventions (test_*.py), include assertions with descriptive failure messages, and produce clean test runs.\n"
        "5. Output Clarity: Present test results with a structured scorecard: total tests run, passed, failed, execution duration, and coverage insights."
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
