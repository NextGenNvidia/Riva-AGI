import logging
from typing import TypedDict, Literal

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from orchestration.orchestrator.agent_registry import AGENT_REGISTRY
from orchestration.orchestrator.router import classify_intent


load_dotenv()

logger = logging.getLogger(__name__)


AgentName = Literal["coder", "researcher", "fallback"]
IntentName = Literal["coding", "research", "unknown"]


class AgentState(TypedDict):
    task: str
    agent: AgentName
    response: str
    task_id: str
    session_id: str
    source: str
    intent: IntentName
    confidence: float


def route_task(state: AgentState):
    try:
        classification = classify_intent(state["task"])

        logger.info(
            "Orchestrator routed task to: %s",
            classification["agent"],
        )

        return {
            "intent": classification["intent"],
            "agent": classification["agent"],
            "confidence": classification["confidence"],
            "task_id": state["task_id"],
            "session_id": state["session_id"],
            "source": state["source"],
        }

    except Exception:
        logger.exception("Failed to classify task")
        raise


def coder_node(state: AgentState):
    try:
        agent = AGENT_REGISTRY["coder"]
        response = agent(state["task"])
        return {"response": response}

    except Exception:
        logger.exception("Coder agent failed")
        raise


def researcher_node(state: AgentState):
    try:
        agent = AGENT_REGISTRY["researcher"]
        response = agent(state["task"])
        return {"response": response}

    except Exception:
        logger.exception("Researcher agent failed")
        raise


def fallback_node(state: AgentState):
    return {
        "response": (
            "I couldn't confidently determine which agent should "
            "handle this task."
        )
    }


def route_decision(state: AgentState) -> AgentName:
    return state["agent"]


def create_orchestrator():
    graph = StateGraph(AgentState)

    graph.add_node("route", route_task)
    graph.add_node("coder", coder_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("fallback", fallback_node)

    graph.add_edge(START, "route")

    graph.add_conditional_edges(
        "route",
        route_decision,
        {
            "coder": "coder",
            "researcher": "researcher",
            "fallback": "fallback",
        },
    )

    graph.add_edge("coder", END)
    graph.add_edge("researcher", END)
    graph.add_edge("fallback", END)

    return graph.compile()


def run_orchestrator(
    task: str,
    task_id: str = "task-001",
    session_id: str = "session-001",
    source: str = "cli",
) -> dict:

    try:
        app = create_orchestrator()

        result = app.invoke(
            {
                "task": task,
                "agent": "fallback",
                "response": "",
                "task_id": task_id,
                "session_id": session_id,
                "source": source,
                "intent": "unknown",
                "confidence": 0.0,
            }
        )

        return result

    except Exception:
        logger.exception(
            "Orchestration failed for task_id=%s",
            task_id,
        )
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    task = input("Enter your task: ")

    result = run_orchestrator(task)

    print("\nFinal response:")
    print(result["response"])