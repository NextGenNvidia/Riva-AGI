"""
Base Autonomous Agent — orchestration/agents/base.py
=====================================================
Defines the BaseAgent class powering all intelligent, self-reflecting,
and tool-calling agents in Riva-AGI.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from orchestration.llm.client import LLMClient, llm_client
from orchestration.llm.prompts import REACT_AGENT_SYSTEM_PROMPT
from orchestration.orchestrator.schemas.input import InputData
from orchestration.orchestrator.schemas.response import AgentResponse, ResponseStatus
from orchestration.orchestrator.schemas.tool import ToolCall, ToolResult
from orchestration.tools.executor import tool_executor
from orchestration.tools.registry import tool_registry

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for autonomous ReAct (Reasoning + Acting) agents in Riva-AGI.
    """

    def __init__(
        self,
        agent_id: str,
        description: str,
        system_prompt: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        llm: Optional[LLMClient] = None,
        max_iterations: int = 6,
    ):
        self.agent_id = agent_id
        self.description = description
        self.system_prompt_template = system_prompt or REACT_AGENT_SYSTEM_PROMPT
        self.tool_names = tool_names or []
        self.llm = llm or llm_client
        self.max_iterations = max_iterations

    def _format_tools_description(self) -> str:
        """Generate human and LLM-readable description of assigned tools."""
        lines = []
        for name in self.tool_names:
            tool_def = tool_registry.get(name)
            if tool_def:
                params_str = ", ".join(f"{p.name}: {p.type_name}" for p in tool_def.parameters)
                lines.append(f"- {name}({params_str}): {tool_def.description}")
            else:
                lines.append(f"- {name}: (Tool registered in system)")
        return "\n".join(lines) if lines else "No external tools assigned."

    def _trim_context_window(self, messages: List[Dict[str, str]], max_messages: int = 12) -> List[Dict[str, str]]:
        """Keep the system prompt and original task, but trim middle conversation to prevent context overflow."""
        if len(messages) <= max_messages:
            return messages
        
        # Keep first 2 (system, user original prompt) and last N-2 (recent interactions)
        trimmed = messages[:2] + messages[-(max_messages - 2):]
        logger.info("Context window trimmed from %d to %d messages.", len(messages), len(trimmed))
        return trimmed

    def _parse_action(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract tool name and parameters from ReAct action syntax, raising ValueError on format errors."""
        action_match = re.search(r"Action:\s*([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        if not action_match:
            return None

        tool_name = action_match.group(1).strip()
        params = {}

        # Extract Action Input JSON
        input_match = re.search(r"Action Input:\s*(\{.*?\}|\[.*?\]|\".*?\")", text, re.DOTALL)
        json_block = re.search(r"Action Input:\s*(\{[\s\S]*?\})", text)
        
        raw_input = None
        if input_match:
            raw_input = input_match.group(1).strip()
        elif json_block:
            raw_input = json_block.group(1).strip()
            
        if raw_input:
            try:
                params = json.loads(raw_input)
                if not isinstance(params, dict):
                    params = {"input": params}
            except json.JSONDecodeError as e:
                # Strong self-correction signal instead of silent fallback
                raise ValueError(f"Failed to parse Action Input as valid JSON. Error: {str(e)}. Please ensure the input is strictly valid JSON format.")
        else:
            # Maybe the tool takes no input, or they just wrote standard text. 
            # We'll see if there's text right after
            fallback_text = text[action_match.end():].strip()
            if fallback_text and not fallback_text.startswith("Observation"):
                params = {"input": fallback_text.split("\n")[0].strip()}

        return {"tool_name": tool_name, "parameters": params}

    def _extract_final_answer(self, text: str) -> Optional[str]:
        """Extract the final response text after ReAct convergence."""
        match = re.search(r"Final Answer:\s*([\s\S]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def run(self, task_payload: InputData) -> AgentResponse:
        """
        Execute the autonomous ReAct reasoning loop.
        """
        start_time = time.perf_counter()
        task_text = task_payload.text_content or ""
        executed_tool_calls: List[ToolCall] = []

        # 1. Prepare system prompt
        tools_desc = self._format_tools_description()
        system_prompt = self.system_prompt_template.replace("{tools_description}", tools_desc)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_text},
        ]

        logger.info("Agent [%s] starting task: '%s'", self.agent_id, task_text[:80])

        final_content = ""
        status = ResponseStatus.SUCCESS

        for iteration in range(self.max_iterations):
            logger.debug("Agent [%s] iteration %d/%d", self.agent_id, iteration + 1, self.max_iterations)
            
            # Context Window Management
            messages = self._trim_context_window(messages)

            # Generate thought/action from LLM
            llm_output = self.llm.generate(
                messages=messages,
                available_tools=self.tool_names,
                iteration=iteration,
            )

            messages.append({"role": "assistant", "content": llm_output})

            # Check if final answer is reached
            final_answer = self._extract_final_answer(llm_output)
            if final_answer:
                final_content = final_answer
                break

            # Parse Action with Self-Correction capability
            try:
                action = self._parse_action(llm_output)
            except ValueError as e:
                # Inject self-correction prompt back to LLM
                obs_text = f"Observation: FORMATTING ERROR - {str(e)}\nPlease rewrite your Action and Action Input using correct JSON."
                messages.append({"role": "user", "content": obs_text})
                continue
                
            if not action:
                # If no action and no explicit final answer tag, treat full output as answer
                final_content = llm_output
                break

            tool_name = action["tool_name"]
            params = action["parameters"]

            # Guardrail: Check authorization
            if tool_name not in self.tool_names:
                obs_text = f"Observation: Error - Tool '{tool_name}' is not in your permitted tools list ({self.tool_names})."
                messages.append({"role": "user", "content": obs_text})
                continue

            # Execute tool
            call_id = f"{self.agent_id}-call-{uuid.uuid4().hex[:6]}"
            tool_call = ToolCall(
                call_id=call_id,
                tool_name=tool_name,
                parameters=params,
                expected_return_type="str",
            )
            executed_tool_calls.append(tool_call)

            tool_res: ToolResult = tool_executor.execute(tool_call)

            if tool_res.success:
                obs_text = f"Observation: {str(tool_res.output)}"
            else:
                obs_text = f"Observation: Tool failed with error: {tool_res.error}. Please reflect and try an alternative approach."

            messages.append({"role": "user", "content": obs_text})

        if not final_content:
            final_content = f"Agent completed {self.max_iterations} iterations. Last state: {messages[-1].get('content', '')}"

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return AgentResponse(
            agent_id=self.agent_id,
            status=status,
            content=final_content,
            tool_calls=executed_tool_calls,
            execution_time_ms=elapsed_ms,
            metadata={
                "iterations": iteration + 1,
                "tools_used": [c.tool_name for c in executed_tool_calls],
                "modality": task_payload.input_type.value,
            },
        )

    def __call__(self, task_payload: InputData) -> AgentResponse:
        """Allow instance to be called directly like a function."""
        return self.run(task_payload)
