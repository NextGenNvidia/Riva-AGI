from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END

from agents.coder import coder_agent
from agents.researcher import researcher_agent

class IntentClassification(TypedDict):
    intent: Literal["coding", "research"]
    agent: Literal["coder", "researcher"]
    confidence: float


class AgentState(TypedDict):
    task: str
    agent: str
    response: str
    task_id: str
    session_id: str
    source: str


def classify_intent(task: str) -> IntentClassification:
    """Classify a task into an agent intent.

    This function is intentionally kept separate from the graph so it can
    later be replaced with an LLM-based intent classifier.
    """
    task_lower = task.lower()

    coding_keywords = [
        "write code",
        "write python code",
        "python code",
        "write a program",
        "create a program",
        "implement",
        "debug",
        "fix this code",
        "create a function",
        "create a class",
        "coding problem",
    ]

    if any(keyword in task_lower for keyword in coding_keywords):
        return {
            "intent": "coding",
            "agent": "coder",
            "confidence": 0.8,
        }

    return {
        "intent": "research",
        "agent": "researcher",
        "confidence": 0.7,
    }


def route_task(state: AgentState):
    classification = classify_intent(state["task"])

    print(
        f"Orchestrator routed task to: "
        f"{classification['agent']}"
    )

    return {
        "agent": classification["agent"]
    }


def coder_node(state: AgentState):
    response = coder_agent(state["task"])
    return {"response": response}


def researcher_node(state: AgentState):
    response = researcher_agent(state["task"])
    return {"response": response}


def route_decision(state: AgentState) -> str:
    return state["agent"]


graph = StateGraph(AgentState)

graph.add_node("route", route_task)
graph.add_node("coder", coder_node)
graph.add_node("researcher", researcher_node)

graph.add_edge(START, "route")

graph.add_conditional_edges(
    "route",
    route_decision,
    {
        "coder": "coder",
        "researcher": "researcher"
    }
)

graph.add_edge("coder", END)
graph.add_edge("researcher", END)

app = graph.compile()


def run_orchestrator(
    task: str,
    task_id: str = "task-001",
    session_id: str = "session-001",
    source: str = "cli"
) -> dict:
    result = app.invoke({
        "task": task,
        "agent": "",
        "response": "",
        "task_id": task_id,
        "session_id": session_id,
        "source": source
    })

    return result


if __name__ == "__main__":
    task = input("Enter your task: ")

    result = run_orchestrator(task)

    print("\nFinal response:")
    print(result["response"])