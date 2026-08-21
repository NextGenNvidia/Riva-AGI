import json
import logging
from pathlib import Path
from typing import Literal, TypedDict
import re

from orchestration.llm.client import llm_client

AgentName = Literal["coder", "researcher", "fallback"]
IntentName = Literal["coding", "research", "unknown"]

class IntentClassification(TypedDict):
    intent: IntentName
    agent: AgentName
    confidence: float

logger = logging.getLogger(__name__)

def classify_intent(task: str) -> IntentClassification:
    """Classify a task using a Smart LLM-based semantic router."""
    task = task.strip()

    # Input guardrail
    if not task:
        return {
            "intent": "unknown",
            "agent": "fallback",
            "confidence": 0.0,
        }

    system_prompt = (
        "You are the Riva-AGI Orchestrator Router. Your job is to classify the user's task.\n"
        "Categories:\n"
        "1. 'coding' -> The user wants to write code, solve algorithmic problems (e.g., LeetCode/array questions), debug, or build software.\n"
        "2. 'research' -> The user wants to find information, search the web, learn about a topic, or summarize data.\n"
        "3. 'system' -> The user wants to know the current date, time, system status, or do a mathematical calculation.\n"
        "4. 'unknown' -> The task doesn't fit any category or is completely ambiguous.\n\n"
        "Output ONLY a raw JSON object (no markdown, no quotes) with this exact schema:\n"
        '{"intent": "coding", "confidence": 0.95}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task}
    ]

    try:
        # Use LLM to generate classification
        response = llm_client.generate(messages=messages)
        
        # Extract JSON block in case LLM adds markdown
        json_match = re.search(r"\{.*?\}", response, re.DOTALL)
        if json_match:
            response = json_match.group(0)
            
        data = json.loads(response)
        intent = data.get("intent", "unknown").lower()
        confidence = float(data.get("confidence", 0.0))

        if intent == "coding":
            return {"intent": "coding", "agent": "coder", "confidence": confidence}
        elif intent == "research":
            return {"intent": "research", "agent": "researcher", "confidence": confidence}
        elif intent == "system":
            return {"intent": "system", "agent": "system", "confidence": confidence}
        else:
            return {"intent": "unknown", "agent": "fallback", "confidence": confidence}
            
    except Exception as e:
        logger.warning("LLM routing failed: %s. Falling back to simple heuristic.", e)
        # Basic fallback heuristic
        task_lower = task.lower()
        if any(k in task_lower for k in ["code", "python", "array", "algorithm", "function", "bug"]):
            return {"intent": "coding", "agent": "coder", "confidence": 0.6}
        elif any(k in task_lower for k in ["search", "find", "who", "what", "explain"]):
            return {"intent": "research", "agent": "researcher", "confidence": 0.6}
        
        return {"intent": "unknown", "agent": "fallback", "confidence": 0.0}