import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

CODER_TOOLS = [
    "read_file",
    "write_file",
    "edit_file",
    "list_directory",
    "execute_command",
    "verify_code_syntax",
    "run_code_tests",
]


@registry.register("coder", AgentCapabilities(description="Handles coding, file creation, software development, syntax verification, and automated testing.", tools=CODER_TOOLS, agent_level="TASK_DOER"))
def coder_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Coder Agent")
    
    start_time = time.time()
    my_key = key_manager.get_api_key_for_role("CODER")
    
    sys_prompt = (
        "You are the Coder Agent in the Riva-AGI autonomous system.\n"
        "You have direct access to the filesystem, command execution, and code verification tools:\n"
        "- Filesystem: read_file, write_file, edit_file, list_directory.\n"
        "- Execution: execute_command.\n"
        "- Verification: verify_code_syntax (checks AST/syntax validity), run_code_tests (runs pytest on test targets).\n"
        "When writing or modifying code:\n"
        "1. Write the code directly to disk using your tools.\n"
        "2. Autonomously verify that your code has valid syntax using verify_code_syntax.\n"
        "3. If tests exist or are requested, execute them using run_code_tests and fix any errors before concluding."
    )
    
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="coder",
        tools=CODER_TOOLS,
        return_tool_calls=True
    )
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="coder",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )