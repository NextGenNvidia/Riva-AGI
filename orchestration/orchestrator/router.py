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


def classify_intent(task: str) -> IntentClassification:
    """Classify a task using configurable routing rules."""

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

    coding_keywords = config["coding"]["keywords"]
    research_keywords = config["research"]["keywords"]

    coding_matches = sum(
        keyword.lower() in task_lower
        for keyword in coding_keywords
    )

    research_matches = sum(
        keyword.lower() in task_lower
        for keyword in research_keywords
    )

    if coding_matches > research_matches and coding_matches > 0:
        return {
            "intent": "coding",
            "agent": "coder",
            "confidence": min(0.6 + (coding_matches * 0.1), 0.95),
        }

    if research_matches > coding_matches and research_matches > 0:
        return {
            "intent": "research",
            "agent": "researcher",
            "confidence": min(0.6 + (research_matches * 0.1), 0.95),
        }

    return {
        "intent": "unknown",
        "agent": "fallback",
        "confidence": 0.0,
    }