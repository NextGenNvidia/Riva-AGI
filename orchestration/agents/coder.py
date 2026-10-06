"""
Coder Agent — orchestration/agents/coder.py
============================================
Autonomous coding agent that generates code via Gemini LLM,
invokes filesystem & execution tools, authorizes operations against
SecurityGate, and persists files to disk.
"""
import ast
import logging
import re
import time
import uuid
from typing import List, Optional

from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini
from orchestration.orchestrator.schemas.tool import ToolCall
from orchestration.orchestrator.security import security_gate
from orchestration.tools.builtin.file_tools import write_file

logger = logging.getLogger(__name__)

CODER_TOOLS = [
    "read_file",
    "write_file",
    "edit_file",
    "list_directory",
    "execute_command",
    "inspect_browser_dom",
    "stream_code_to_editor",
]


def _extract_filename(text: str) -> Optional[str]:
    """Detects a filename if explicitly requested in the prompt or instruction."""
    match = re.search(r"['\"]?([a-zA-Z0-9_\-\.\/\\]+\.(?:py|json|md|txt|html|css|js|ts|sh|yaml|yml))['\"]?", text, re.IGNORECASE)
    if match:
        return match.group(1).replace("'", "").replace('"', "")
    return None


def _extract_code(content: str) -> Optional[str]:
    """Extracts code blocks from markdown fences if present."""
    code_match = re.search(r"```(?:[a-zA-Z0-9_-]+)?\s*\n(.*?)\n```", content, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    return None


@registry.register("coder", AgentCapabilities(description="Handles coding, file creation, software development, and testing tasks.", tools=CODER_TOOLS, agent_level="TASK_DOER"))
def coder_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Coder Agent")
    start_time = time.time()
    
    prompt_text = task_data.text_content or ""
    my_key = key_manager.get_api_key_for_role("CODER")
    
    sys_prompt = (
        "You are the Lead Autonomous Software Engineer (Coder Agent) in the Riva-AGI framework.\n"
        "Your mission is to produce robust, complete, production-grade software deliverables that fulfill user requirements without placeholders.\n\n"
        "OPERATIONAL PROTOCOLS:\n"
        "1. Direct Tool Execution: You have direct access to tools: read_file, write_file, edit_file, list_directory, and execute_command. "
        "When requested to create, modify, or inspect code, actively invoke these tools on the filesystem rather than merely printing code blocks.\n"
        "2. Context Awareness: Before modifying existing files, inspect their contents using read_file or list_directory to understand existing architectures and prevent regressions.\n"
        "3. Production Quality: Write complete, functional code with all necessary imports, docstrings, error handling, and type hints. "
        "Never use placeholder comments such as '// TODO' or 'pass' in core logic.\n"
        "4. Syntax & Execution Verification: After creating or editing code, verify syntax using execute_command or file tools to ensure clean execution.\n"
        "5. Output Clarity: Conclude with a concise technical summary detailing modified files, design decisions, and verification status."
    )
    
    try:
        content, tool_calls = call_gemini(
            prompt=prompt_text,
            api_key=my_key,
            system_instruction=sys_prompt,
            agent_id="coder",
            tools=CODER_TOOLS,
            return_tool_calls=True
        )
    except Exception as e:
        logger.error(f"Coder agent LLM invocation failed: {e}")
        content = f"Error during code generation: {e}"
        tool_calls = []

    content = content or ""
    target_filename = _extract_filename(prompt_text)

    # If the user explicitly requested a file to be written, ensure file is on disk
    if target_filename and content and not any(tc.tool_name == "write_file" for tc in tool_calls):
        code_block = _extract_code(content)
        code_to_write = code_block if code_block is not None else content

        allowed, reason = security_gate.evaluate_tool_call(
            tool_name="write_file",
            args={"file_path": target_filename, "content": code_to_write},
            caller_agent="coder"
        )

        if allowed:
            write_res = write_file(file_path=target_filename, content=code_to_write, overwrite=True)
            logger.info(f"[Coder Agent] File write execution: {write_res}")
            tool_calls.append(
                ToolCall(
                    call_id=str(uuid.uuid4()),
                    tool_name="write_file",
                    parameters={"file_path": target_filename, "characters": len(code_to_write)},
                    expected_return_type="str"
                )
            )
        else:
            logger.error(f"[Coder Agent] SecurityGate rejected write_file: {reason}")
            content += f"\n\n[Security Gate Block]: {reason}"

    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="coder",
        status=ResponseStatus.SUCCESS if not content.startswith("Error during code generation") else ResponseStatus.FAILURE,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value, "target_file": target_filename}
    )