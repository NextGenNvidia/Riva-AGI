import logging
import json
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from orchestration.orchestrator.registry import registry
from orchestration.orchestrator.state_manager import TaskStateManager, TaskStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.router import classify_intent
from orchestration import InputData, AgentResponse, ResponseStatus, InputType

# Level 2 Managers
import orchestration.orchestrator.intent_classifier
import orchestration.orchestrator.planner
import orchestration.orchestrator.executor
import orchestration.orchestrator.reviewer

# Level 3 Task-Doers
import orchestration.agents.coder
import orchestration.agents.researcher
import orchestration.agents.writer
import orchestration.agents.reasoner
import orchestration.agents.designer
import orchestration.agents.qa_tester
import orchestration.agents.data_analyst
import orchestration.agents.devops
import orchestration.agents.security_auditor
import orchestration.agents.seo_specialist
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
    
    # Hierarchical State Variables
    complexity: str # "simple" or "complex"
    routing_decision: str # target agent or action ("delegate", "review")
    plan: list[dict] # [{"agent": "coder", "task": "..."}]
    current_step: int # index of the current plan step
    completed_steps: list[dict] # [{"agent": "...", "result": "..."}]
    feedback: str # feedback from reviewer
    
    intent: str
    confidence: float


def clean_json(text: str) -> str:
    """Helper to clean markdown json blocks."""
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def intent_node(state: AgentState):
    task_id = state["task_id"]
    task_text = state["task_payload"].text_content or ""
    task_manager.start_task(task_id=task_id, initial_data={"task": task_text})
    task_manager.update_task_state(task_id, "intent_classifier", TaskStatus.IN_PROGRESS)
    
    handler = registry.get_agent("intent_classifier")
    response = handler(state["task_payload"])
    
    try:
        data = json.loads(clean_json(response.content))
        complexity = data.get("complexity", "simple")
        routing_decision = data.get("target_agent", "fallback")
    except Exception:
        complexity = "simple"
        routing_decision = "fallback"
        
    task_manager.update_task_state(task_id, "intent_classifier", TaskStatus.COMPLETED)
    
    return {
        "complexity": complexity, 
        "routing_decision": routing_decision,
        "agent": routing_decision
    }

def planner_node(state: AgentState):
    task_id = state["task_id"]
    task_manager.update_task_state(task_id, "planner", TaskStatus.IN_PROGRESS)
    
    handler = registry.get_agent("planner")
    response = handler(state["task_payload"])
    
    try:
        plan = json.loads(clean_json(response.content))
    except Exception:
        plan = []
        
    task_manager.update_task_state(task_id, "planner", TaskStatus.COMPLETED)
    return {"plan": plan, "current_step": 0, "completed_steps": []}

def executor_node(state: AgentState):
    task_id = state["task_id"]
    task_manager.update_task_state(task_id, "executor", TaskStatus.IN_PROGRESS)
    
    # Let executor see the plan and what's done
    executor_prompt = f"Plan: {json.dumps(state['plan'])}\nCompleted: {json.dumps(state['completed_steps'])}"
    from orchestration import InputData, InputType
    temp_payload = InputData(input_type=InputType.TEXT, text_content=executor_prompt)
    
    handler = registry.get_agent("executor")
    response = handler(temp_payload)
    
    try:
        data = json.loads(clean_json(response.content))
        action = data.get("action", "delegate")
        target = data.get("target", "fallback")
    except Exception:
        action = "review"
        target = "reviewer"
        
    task_manager.update_task_state(task_id, "executor", TaskStatus.COMPLETED)
    return {"routing_decision": target, "agent": target}

def reviewer_node(state: AgentState):
    task_id = state["task_id"]
    task_manager.update_task_state(task_id, "reviewer", TaskStatus.IN_PROGRESS)
    
    review_prompt = f"Original: {state['task_payload'].text_content}\nOutput: {json.dumps(state['completed_steps'])}"
    from orchestration import InputData, InputType
    temp_payload = InputData(input_type=InputType.TEXT, text_content=review_prompt)
    
    handler = registry.get_agent("reviewer")
    response = handler(temp_payload)
    
    try:
        data = json.loads(clean_json(response.content))
        status = data.get("status", "approved")
        feedback = data.get("feedback", "")
    except Exception:
        status = "approved"
        feedback = ""
        
    task_manager.update_task_state(task_id, "reviewer", TaskStatus.COMPLETED)
    return {"routing_decision": status, "feedback": feedback, "response_payload": response}

def create_agent_node(agent_name: str):
    def node_func(state: AgentState):
        task_id = state["task_id"]
        task_manager.update_task_state(task_id, agent_name, TaskStatus.IN_PROGRESS)
        
        handler = registry.get_agent(agent_name)
        response = handler(state["task_payload"])
        
        # Append to completed steps if in a complex loop
        completed = list(state.get("completed_steps", []))
        completed.append({"agent": agent_name, "result": response.content})
        
        task_manager.update_task_state(task_id, agent_name, TaskStatus.COMPLETED)
        return {"response_payload": response, "completed_steps": completed}
    return node_func

def fallback_node(state: AgentState):
    task_id = state["task_id"]
    task_manager.update_task_state(task_id, "fallback", TaskStatus.FAILED)
    return {"routing_decision": "approved"}

def route_after_intent(state: AgentState) -> str:
    if state["complexity"] == "complex":
        return "planner"
    return state["routing_decision"]

def route_after_executor(state: AgentState) -> str:
    if state["routing_decision"] == "reviewer":
        return "reviewer"
    return state["routing_decision"]
    
def route_after_worker(state: AgentState) -> str:
    if state["complexity"] == "complex":
        return "executor"
    return END
    
def route_after_reviewer(state: AgentState) -> str:
    if state["routing_decision"] == "rejected":
        return "executor"
    return END

def create_orchestrator():
    graph = StateGraph(AgentState)

    graph.add_node("intent", intent_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("fallback", fallback_node)
    
    # Add Worker Agents
    registered_agents = registry.get_all_capabilities().keys()
    workers = [a for a in registered_agents if a not in ["intent_classifier", "planner", "executor", "reviewer"]]
    for agent_name in workers:
        graph.add_node(agent_name, create_agent_node(agent_name))
        
    graph.add_edge(START, "intent")

    # Intent routing
    intent_map = {w: w for w in workers}
    intent_map["planner"] = "planner"
    intent_map["fallback"] = "fallback"
    graph.add_conditional_edges("intent", route_after_intent, intent_map)
    
    # Planner -> Executor
    graph.add_edge("planner", "executor")
    
    # Executor routing
    exec_map = {w: w for w in workers}
    exec_map["reviewer"] = "reviewer"
    exec_map["fallback"] = "fallback"
    graph.add_conditional_edges("executor", route_after_executor, exec_map)
    
    # Worker routing (back to executor if complex, else END)
    for agent_name in workers:
        graph.add_conditional_edges(agent_name, route_after_worker, {"executor": "executor", END: END})
        
    # Reviewer routing
    graph.add_conditional_edges("reviewer", route_after_reviewer, {"executor": "executor", END: END})
    graph.add_edge("fallback", END)

    return graph.compile()


def run_orchestrator(
    task_text: str,
    task_id: str = None,
    session_id: str = "session-001",
    source: str = "cli",
) -> dict:

    try:
        import uuid
        if task_id is None:
            task_id = f"task-{uuid.uuid4().hex[:8]}"

        # Orchestrator (CEO) dynamically loads its API key here
        ceo_key = key_manager.get_api_key_for_role("CEO")
        masked_ceo_key = f"{ceo_key[:8]}...{ceo_key[-4:]}" if ceo_key else "No Key Found"
        logger.info(f"[CEO Orchestrator] Initialized with API Key: {masked_ceo_key}")

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
                "complexity": "simple",
                "routing_decision": "fallback",
                "plan": [],
                "current_step": 0,
                "completed_steps": [],
                "feedback": "",
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
    
    # Allow dynamic testing from terminal or fallback to a dummy task
    task = input("\nEnter your task (or press Enter for a dummy test): ").strip()
    if not task:
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
    final_history = task_manager.get_task_status(result["task_id"])
    print(final_history.model_dump_json(indent=2))
