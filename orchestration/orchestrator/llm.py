import logging
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
except ImportError:
    genai = None
    types = None
    APIError = Exception

logger = logging.getLogger(__name__)

# Define the Multi-Model Architecture Mapping
MODEL_MAPPING = {
    # Level 2 Managers (High Reasoning & Orchestration)
    "intent_classifier": "gemini-3.5-flash-lite",  # Called frequently, needs high RPM
    "executor": "gemini-3.5-flash-lite",           # Called frequently in loops
    "planner": "gemini-3.5-flash",                   # Deep reasoning, called once
    "reviewer": "gemini-3.5-flash",                  # Deep reasoning, called once
    
    # Level 3 Complex Workers (Balanced)
    "coder": "gemini-3.1-flash-lite",
    "reasoner": "gemini-3.1-flash-lite",
    "devops": "gemini-3.1-flash-lite",
    "security_auditor": "gemini-3.1-flash-lite",
    
    # Level 3 Standard Workers (Fast Execution)
    "writer": "gemini-3.5-flash-lite",
    "designer": "gemini-3.5-flash-lite",
    "qa_tester": "gemini-3.1-flash-lite",
    "data_analyst": "gemini-3.1-flash-lite",
    "seo_specialist": "gemini-3.1-flash-lite",
    "researcher": "gemini-3.5-flash-lite",
    "dummy_system": "gemini-3.5-flash-lite"
}

import functools
import inspect
import uuid
from typing import List, Callable, Optional, Tuple, Dict, Any
from orchestration.orchestrator.schemas.tool import ToolCall

def call_gemini(
    prompt: str,
    api_key: str,
    system_instruction: str,
    agent_id: str,
    tools: Optional[List[Callable]] = None,
    return_tool_calls: bool = False
) -> str | Tuple[str, List[ToolCall]]:
    """
    Calls the Google GenAI SDK using the specific model assigned to the agent.
    Supports automatic function calling with tool execution tracking.
    """
    if not api_key:
        raise ValueError(f"API Key is missing for agent [{agent_id}].")
    model_name = MODEL_MAPPING.get(agent_id, "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)
    
    executed_tool_calls: List[ToolCall] = []
    
    # Wrap tools with functools.wraps to preserve signatures for GenAI SDK
    wrapped_tools = None
    if tools:
        wrapped_tools = []
        for t in tools:
            def make_wrapper(fn):
                @functools.wraps(fn)
                def wrapper(*args, **kwargs):
                    # Bind positional args to kwargs
                    sig = inspect.signature(fn)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    call_params = bound.arguments
                    
                    logger.info(f"Agent [{agent_id}] executing tool -> {fn.__name__}({call_params})")
                    try:
                        res = fn(*args, **kwargs)
                        call_obj = ToolCall(
                            call_id=f"call-{uuid.uuid4().hex[:8]}",
                            tool_name=fn.__name__,
                            parameters=call_params,
                            expected_return_type="str"
                        )
                        executed_tool_calls.append(call_obj)
                        return res
                    except Exception as err:
                        err_msg = f"Error in {fn.__name__}: {err}"
                        logger.error(err_msg)
                        call_obj = ToolCall(
                            call_id=f"call-{uuid.uuid4().hex[:8]}",
                            tool_name=fn.__name__,
                            parameters=call_params,
                            expected_return_type="str"
                        )
                        executed_tool_calls.append(call_obj)
                        return err_msg
                return wrapper
            wrapped_tools.append(make_wrapper(t))
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.7,
        tools=wrapped_tools if wrapped_tools else None
    )
    
    def extract_text(resp) -> str:
        if not resp:
            return ""
        if resp.text:
            return resp.text
        # Fallback extraction from candidates
        if hasattr(resp, "candidates") and resp.candidates:
            parts = []
            for cand in resp.candidates:
                if hasattr(cand, "content") and cand.content and hasattr(cand.content, "parts"):
                    for part in cand.content.parts:
                        if hasattr(part, "text") and part.text:
                            parts.append(part.text)
            if parts:
                return "\n".join(parts)
        return ""

    final_text = ""
    try:
        logger.info(f"Agent [{agent_id}] triggering LLM -> {model_name} (tools={len(tools) if tools else 0})")
        if wrapped_tools:
            chat = client.chats.create(model=model_name, config=config)
            response = chat.send_message(prompt)
        else:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
        final_text = extract_text(response)
        if not final_text and wrapped_tools:
            try:
                for msg in reversed(chat.get_history()):
                    if getattr(msg, "role", "") == "model":
                        for part in getattr(msg, "parts", []):
                            if getattr(part, "text", None):
                                final_text = part.text
                                break
                    if final_text:
                        break
            except Exception:
                pass
    except APIError as e:
        logger.warning(f"Agent [{agent_id}] failed with model {model_name}: {e}. Falling back to gemini-3.5-flash-lite")
        try:
            if wrapped_tools:
                chat = client.chats.create(model="gemini-3.5-flash-lite", config=config)
                response = chat.send_message(prompt)
            else:
                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=config
                )
            final_text = extract_text(response)
            if not final_text and wrapped_tools:
                try:
                    for msg in reversed(chat.get_history()):
                        if getattr(msg, "role", "") == "model":
                            for part in getattr(msg, "parts", []):
                                if getattr(part, "text", None):
                                    final_text = part.text
                                    break
                        if final_text:
                            break
                except Exception:
                    pass
        except Exception as fallback_e:
            final_text = f"LLM Generation Failed on Fallback: {fallback_e}"
    except Exception as e:
        final_text = f"LLM Generation Error: {e}"

    if not final_text and executed_tool_calls:
        tool_names = [tc.tool_name for tc in executed_tool_calls]
        final_text = f"Successfully executed tools: {', '.join(tool_names)}."

    if return_tool_calls:
        return final_text, executed_tool_calls
    return final_text
