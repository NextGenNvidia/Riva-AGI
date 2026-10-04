import logging
import functools
import time
import uuid
from typing import Optional, List, Callable, Any, Tuple, Union

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
except ImportError:
    genai = None
    types = None
    APIError = Exception

from orchestration.tools import tool_registry
from orchestration.orchestrator.schemas.tool import ToolCall, ToolResult
from orchestration.orchestrator.config import key_manager

logger = logging.getLogger(__name__)

# High-quota, active models for free-tier resilience (1,500 RPD / 15-30 RPM)
PRIMARY_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]

MODEL_MAPPING = {
    # Level 2 Managers (High Reasoning & Orchestration)
    "intent_classifier": "gemini-3.5-flash-lite",
    "executor": "gemini-3.5-flash-lite",
    "planner": "gemini-3.5-flash-lite",
    "reviewer": "gemini-3.5-flash-lite",
    
    # Level 3 Complex Workers (Balanced)
    "coder": "gemini-3.5-flash-lite",
    "reasoner": "gemini-3.5-flash-lite",
    "devops": "gemini-3.5-flash-lite",
    "security_auditor": "gemini-3.5-flash-lite",
    
    # Level 3 Standard Workers (Fast Execution)
    "writer": "gemini-3.5-flash-lite",
    "designer": "gemini-3.5-flash-lite",
    "qa_tester": "gemini-3.5-flash-lite",
    "data_analyst": "gemini-3.5-flash-lite",
    "seo_specialist": "gemini-3.5-flash-lite",
    "researcher": "gemini-3.5-flash-lite",
    "dummy_system": "gemini-3.5-flash-lite"
}


def _wrap_tool_for_execution(name: str, func: Callable, execution_log: list) -> Callable:
    """
    Wraps a tool function to track its execution time, parameters, and output
    for audit trails, schemas, and UI telemetry.
    """
    @functools.wraps(func)
    def tracked_tool(*args, **kwargs):
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        logger.info(f"LLM triggered tool [{name}] with args: {kwargs}")
        
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000.0
            
            tool_call = ToolCall(
                call_id=call_id,
                tool_name=name,
                parameters=kwargs,
                expected_return_type=str(type(result).__name__)
            )
            execution_log.append(tool_call)
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            error_msg = f"Tool Execution Error ({name}): {str(e)}"
            logger.error(error_msg)
            
            tool_call = ToolCall(
                call_id=call_id,
                tool_name=name,
                parameters=kwargs,
                expected_return_type="str"
            )
            execution_log.append(tool_call)
            return error_msg

    return tracked_tool


def call_gemini(
    prompt: str,
    api_key: str,
    system_instruction: str,
    agent_id: str,
    tools: Optional[List[Union[str, Callable]]] = None,
    return_tool_calls: bool = False
) -> Union[str, Tuple[str, List[ToolCall]]]:
    """
    Calls the Google GenAI SDK using the specific model assigned to the agent,
    with full support for autonomous multi-turn tool calling, 429 quota resilience,
    and automatic API key rotation across the 15-key pool.
    """
    if not api_key:
        api_key = key_manager.get_api_key_for_role(agent_id)
        if not api_key:
            raise ValueError(f"API Key is missing for agent [{agent_id}].")
        
    model_name = MODEL_MAPPING.get(agent_id, PRIMARY_MODEL)
    
    executed_tools: List[ToolCall] = []
    wrapped_tools: List[Callable] = []
    
    # Resolve tools from tool_registry or direct callables
    if tools:
        for t in tools:
            if isinstance(t, str):
                tool_func = tool_registry.get_tool(t)
                if tool_func:
                    wrapped_tools.append(_wrap_tool_for_execution(t, tool_func, executed_tools))
                else:
                    logger.warning(f"Tool '{t}' requested by agent '{agent_id}' was not found in tool_registry.")
            elif callable(t):
                tool_name = getattr(t, "__name__", "custom_tool")
                wrapped_tools.append(_wrap_tool_for_execution(tool_name, t, executed_tools))
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.7,
        tools=wrapped_tools if wrapped_tools else None
    )
    
    # Build candidate model list with high-quota Lite models first
    candidate_models = [model_name] + [m for m in FALLBACK_MODELS if m != model_name]
    candidate_keys = [api_key] + key_manager.get_fallback_keys(api_key)
    
    content = ""
    last_error = None
    success = False
    
    for current_key in candidate_keys:
        client = genai.Client(api_key=current_key)
        for current_model in candidate_models:
            try:
                logger.info(f"Agent [{agent_id}] invoking LLM -> {current_model} (tools: {len(wrapped_tools)})")
                chat = client.chats.create(model=current_model, config=config)
                response = chat.send_message(prompt)
                content = response.text or ""
                last_error = None
                success = True
                break
            except APIError as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning(f"Agent [{agent_id}] hit 429 quota limit on {current_model}. Rotating model/key...")
                    last_error = e
                    continue
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    logger.warning(f"Agent [{agent_id}] model {current_model} not found (404). Trying next model...")
                    last_error = e
                    continue
                else:
                    logger.warning(f"Agent [{agent_id}] encountered APIError on {current_model}: {e}")
                    last_error = e
                    continue
            except Exception as e:
                logger.error(f"Agent [{agent_id}] encountered unexpected error on {current_model}: {e}")
                last_error = e
                break
        if success:
            break
            
    if not success and last_error:
        content = f"LLM Generation Error: {last_error}"
        
    if return_tool_calls:
        return content, executed_tools
    return content
