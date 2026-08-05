import logging
import json
from typing import TypedDict, Literal

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from orchestration.orchestrator.registry import registry
from orchestration.orchestrator.state_manager import TaskStateManager, TaskStatus
from orchestration.orchestrator.router import classify_intent
from orchestration import InputData, AgentResponse, ResponseStatus, InputType

# Ensure all agents are loaded and registered
import orchestration.agents.coder
import orchestration.agents.researcher
import orchestration.agents.dummy_system_agent

load_dotenv()

logger = logging.getLogger(__name__)

# Single global State Manager
task_manager = TaskStateManager()

class AgentState(TypedDict):
    # Now we store the schema-validated objects!
    task_payload: InputData
    agent: str
    response_payload: AgentResponse | None
    task_id: str
    session_id: str
    source: str
    intent: str
    confidence: float


def route_task(state: AgentState):
    try:
        task_text = state["task_payload"].text_content
        task_id = state["task_id"]
        
        # Log state: Started
        task_manager.start_task(
            task_id=task_id, 
            initial_data={"task": task_text}
        )
        
        # Determine Routing
        classification = classify_intent(task_text)
        chosen_agent = classification["agent"]
        
        # Check if the chosen agent actually exists in our dynamic registry
        all_agents = registry.get_all_capabilities()
        if chosen_agent not in all_agents:
            chosen_agent = "fallback"

        logger.info(f"Orchestrator routed task to: {chosen_agent}")
        
        # Update state: In Progress
        task_manager.update_task_state(
            task_id=task_id, 
            new_owner="orchestrator_router", 
            status=TaskStatus.IN_PROGRESS
        )

        return {
            "intent": classification["intent"],
            "agent": chosen_agent,
            "confidence": classification["confidence"],
            "task_id": task_id,
            "session_id": state["session_id"],
            "source": state["source"],
        }

    except Exception:
        logger.exception("Failed to classify task")
        raise


def create_agent_node(agent_name: str):
    """Dynamically generates a LangGraph node function for a given registered agent."""
    def node_func(state: AgentState):
        try:
            task_id = state["task_id"]
            
            # Update state manager tracker
            task_manager.update_task_state(
                task_id=task_id, 
                new_owner=agent_name, 
                status=TaskStatus.IN_PROGRESS
            )
            
            # Fetch handler from registry and execute
            handler = registry.get_agent(agent_name)
            if not handler:
                raise ValueError(f"Agent {agent_name} not found in registry.")
                
            response = handler(state["task_payload"])
            
            # Update state manager tracker on completion
            task_manager.update_task_state(
                task_id=task_id, 
                new_owner=agent_name, 
                status=TaskStatus.COMPLETED
            )
            
            return {"response_payload": response}
            
        except Exception:
            logger.exception(f"{agent_name.capitalize()} agent failed")
            # Update state manager tracker on failure
            task_manager.update_task_state(
                task_id=state["task_id"], 
                new_owner=agent_name, 
                status=TaskStatus.FAILED
            )
            raise
    return node_func


def fallback_node(state: AgentState):
    task_id = state["task_id"]
    task_manager.update_task_state(task_id, new_owner="fallback", status=TaskStatus.FAILED)
    
    fallback_response = AgentResponse(
        agent_id="fallback",
        status=ResponseStatus.FAILED,
        content="I couldn't confidently determine which agent should handle this task.",
        tool_calls=[],
        execution_time_ms=0.0
    )
    return {"response_payload": fallback_response}


def route_decision(state: AgentState) -> str:
    return state["agent"]


def create_orchestrator():
    graph = StateGraph(AgentState)

    graph.add_node("route", route_task)
    
    # 1. Dynamically add all agents from Registry
    registered_agents = registry.get_all_capabilities().keys()
    for agent_name in registered_agents:
        graph.add_node(agent_name, create_agent_node(agent_name))
        
    graph.add_node("fallback", fallback_node)
    graph.add_edge(START, "route")

    # 2. Setup Conditional Edges
    condition_map = {agent: agent for agent in registered_agents}
    condition_map["fallback"] = "fallback"
    
    graph.add_conditional_edges(
        "route",
        route_decision,
        condition_map,
    )

    # 3. All agents route to END
    for agent_name in registered_agents:
        graph.add_edge(agent_name, END)
        
    graph.add_edge("fallback", END)

    return graph.compile()


def run_orchestrator(
    task_text: str,
    task_id: str = "task-final-int",
    session_id: str = "session-001",
    source: str = "cli",
) -> dict:

    try:
        app = create_orchestrator()
        
        # Package the raw string into our strict Schema
        input_data = InputData(
            input_type=InputType.TEXT,
            text_content=task_text,
            metadata={"source": source}
        )

        result = app.invoke(
            {
                "task_payload": input_data,
                "agent": "fallback",
                "response_payload": None,
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
    
    print("="*60)
    print("  Riva-AGI: FULL INTEGRATION RUN (O1, O2, O3, O4)")
    print("="*60)
    
    # Let's use a dynamic agent to prove it works!
    task = "I need to write code for a new feature."
    print(f"\nUser Request: {task}\n")
    
    result = run_orchestrator(task)

    print("\n" + "="*60)
    print("  FINAL AGENT RESPONSE (O2 SCHEMA)")
    print("="*60)
    print(result["response_payload"].model_dump_json(indent=2))
    
    print("\n" + "="*60)
    print("  FINAL TASK HISTORY (O3 TRACKER)")
    print("="*60)
    final_history = task_manager.get_task_status("task-final-int")
    print(final_history.model_dump_json(indent=2))
