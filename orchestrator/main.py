from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from agents.coder import coder_agent
from agents.researcher import researcher_agent


class AgentState(TypedDict):
    task: str
    agent: str
    response: str


def route_task(state: AgentState):
    task = state["task"].lower()

    if "code" in task or "python" in task or "program" in task:
        agent = "coder"
    else:
        agent = "researcher"

    print(f"Orchestrator routed task to: {agent}")

    return {"agent": agent}


def call_agent(state: AgentState):
    task = state["task"]

    if state["agent"] == "coder":
        response = coder_agent(task)
    else:
        response = researcher_agent(task)

    return {"response": response}


graph = StateGraph(AgentState)

graph.add_node("route", route_task)
graph.add_node("agent", call_agent)

graph.add_edge(START, "route")
graph.add_edge("route", "agent")
graph.add_edge("agent", END)

app = graph.compile()


if __name__ == "__main__":
    task = input("Enter your task: ")

    result = app.invoke({
        "task": task,
        "agent": "",
        "response": ""
    })

    print("\nFinal response:")
    print(result["response"])