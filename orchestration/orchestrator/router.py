import json
from pathlib import Path
from typing import Literal, TypedDict


AgentName = Literal["coder", "researcher", "fallback"]
IntentName = Literal["coding", "research", "unknown"]


class IntentClassification(TypedDict):
    intent: IntentName
    agent: AgentName
    confidence: float


CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "routing.json"
)


def load_routing_config() -> dict:
    """Load routing rules from the project configuration."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def classify_intent(task: str) -> dict:
    """Classify a task using configurable routing rules dynamically."""

    task = task.strip()

    # Input guardrail
    if not task:
        return {
            "intent": "unknown",
            "agent": "fallback",
            "confidence": 0.0,
        }

    task_lower = task.lower()
    config = load_routing_config()

    best_intent = "unknown"
    best_agent = "fallback"
    max_matches = 0

    # Dynamically score every intent defined in the config
    for intent_name, intent_data in config.items():
        agent_name = intent_data["agent"]
        keywords = intent_data["keywords"]
        
        matches = sum(keyword.lower() in task_lower for keyword in keywords)
        
        if matches > max_matches:
            max_matches = matches
            best_intent = intent_name
            best_agent = agent_name

    if max_matches > 0:
        return {
            "intent": best_intent,
            "agent": best_agent,
            "confidence": min(0.6 + (max_matches * 0.1), 0.95),
        }

    return {
        "intent": "unknown",
        "agent": "fallback",
        "confidence": 0.0,
    }