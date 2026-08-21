"""
Mock LLM Engine — orchestration/llm/mock_engine.py
===================================================
High-fidelity offline LLM simulation engine for tests, CI/CD,
and local development without requiring external API credits.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockLLMEngine:
    """
    Simulates LLM completions, ReAct reasoning steps, and tool calls for testing.
    """

    def generate_step(
        self,
        messages: List[Dict[str, str]],
        available_tools: List[str],
        iteration: int = 0,
    ) -> str:
        """
        Generate a simulated ReAct step based on prompt contents and iteration count.
        """
        user_message = ""
        last_observation = ""

        for msg in messages:
            content = msg.get("content", "")
            if msg.get("role") == "user" and not content.startswith("Observation:"):
                user_message = content
            if "Observation:" in content:
                last_observation = content.split("Observation:")[-1].strip()

        system_msg = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        user_lower = user_message.lower()

        # Handle Mocking for the Smart LLM Router
        if "Riva-AGI Orchestrator Router" in system_msg:
            if any(w in user_lower for w in ["code", "python", "function", "array", "algorithm", "sort"]):
                return '{"intent": "coding", "confidence": 0.9}'
            elif any(w in user_lower for w in ["research", "explain", "why"]):
                return '{"intent": "research", "confidence": 0.9}'
            else:
                return '{"intent": "unknown", "confidence": 0.0}'

        # Step 2: If we already have an observation from a tool execution, finalize
        if last_observation and iteration > 0:
            return (
                f"Thought: I have observed the tool execution result and can formulate the final answer.\n"
                f"Final Answer: Completed successfully. Result details:\n{last_observation}"
            )

        # Step 1: Decide tool call based on keywords
        if "coder" in available_tools or "execute_python_code" in available_tools:
            if any(w in user_lower for w in ["code", "python", "function", "fibonacci", "calculate", "script", "program"]):
                # Simulate Coder agent calling execute_python_code
                sample_code = "def solve():\n    return 'Execution verified successfully.'\nprint(solve())"
                if "fibonacci" in user_lower:
                    sample_code = "def fib(n):\n    return [0, 1, 1, 2, 3, 5, 8][:n]\nprint('Fibonacci:', fib(7))"
                
                return (
                    f"Thought: The user requested a coding task. I will write and execute the Python code.\n"
                    f"Action: execute_python_code\n"
                    f'Action Input: {{"code": "{sample_code.replace(chr(10), "\\n")}"}}'
                )

        if "web_search" in available_tools and any(w in user_lower for w in ["search", "research", "what is", "who is", "find", "latest"]):
            query = user_message.replace("search", "").replace("research", "").strip() or "Riva AGI system"
            return (
                f"Thought: I need to search the web to gather up-to-date information.\n"
                f"Action: web_search\n"
                f'Action Input: {{"query": "{query}"}}'
            )

        if "get_current_time" in available_tools and any(w in user_lower for w in ["time", "date", "clock", "today"]):
            return (
                "Thought: The user is asking for the current time. I will use get_current_time.\n"
                "Action: get_current_time\n"
                'Action Input: {}'
            )

        if "calculate" in available_tools and any(w in user_lower for w in ["+", "-", "*", "/", "math", "calc"]):
            clean_expr = re.sub(r"[^\d\+\-\*\/\(\)\.\s]", "", user_message).strip() or "42 * 2"
            return (
                f"Thought: I will evaluate the mathematical expression.\n"
                f"Action: calculate\n"
                f'Action Input: {{"expression": "{clean_expr}"}}'
            )

        # Default direct answer
        return (
            f"Thought: I can answer this request directly without calling external tools.\n"
            f"Final Answer: [Riva-AGI Response] Processed request: '{user_message}' with standard autonomous reasoning."
        )


mock_llm_engine = MockLLMEngine()
