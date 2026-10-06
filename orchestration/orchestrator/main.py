"""
Riva-AGI Orchestrator Engine — orchestration/orchestrator/main.py
==================================================================
Dual-Track Low-Latency Multi-Agent Orchestrator featuring:
- Zero-LLM Orchestration Core (Laya Decision Engine ~33ms + Deterministic 0ms DAG Scheduler)
- Structured TaskSpec Handoff with Kahn Cycle Detection
- Agent-Aware Reviewer Quality Profiles with Noul (<35ms) and Retry Cap (max_retries=3)
- Tool-calling integration with SecurityGate authorization
"""
import os
import sys

# Ensure the root directory is in the Python path so absolute imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import logging
import json
import time
import uuid
from typing import TypedDict, List, Dict, Any, Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from orchestration.orchestrator.registry import registry
from orchestration.orchestrator.state_manager import TaskStateManager, TaskStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.router import classify_intent
from orchestration.orchestrator.laya_engine import laya_engine
from orchestration.orchestrator.dag_scheduler import DAGScheduler
from orchestration.orchestrator.schemas.task_spec import TaskSpec, TaskStatus as SpecTaskStatus
from orchestration.orchestrator.whiteboard import WhiteboardContext
from orchestration.orchestrator.aggregator import format_executive_deliverable
from orchestration.orchestrator.security import security_gate
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
import orchestration.agents.knowledge_agent

load_dotenv()

logger = logging.getLogger(__name__)

# Single global State Manager
task_manager = TaskStateManager()

class AgentState(TypedDict):
    task_payload: InputData
    agent: str
    response_payload: Optional[AgentResponse]
    task_id: str
    session_id: str
    source: str
    
    # Hierarchical & DAG State Variables
    complexity: str               # "simple" or "complex"
    routing_decision: str         # target agent or action ("planner", "reviewer", "fallback", etc.)
    plan: List[Dict[str, Any]]    # List of serialized TaskSpec dicts
    current_step: int             # Step index counter
    current_task_id: Optional[str]# ID of the active subtask (e.g. "task_01")
    completed_steps: List[Dict[str, Any]]  # List of completed subtask outputs
    feedback: str                 # Reviewer feedback critique
    retry_count: int              # Counter for retry attempts
    max_retries: int              # Safety cap to prevent infinite rejection loop
    
    intent: str
    confidence: float
    whiteboard: WhiteboardContext
    start_time: float

def clean_json(text: str) -> str:
    """Helper to clean markdown json blocks."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

def safe_update_task_state(task_id: str, owner: str, status: TaskStatus, initial_text: str = "") -> None:
    try:
        task_manager.update_task_state(task_id, owner, status)
    except ValueError:
        try:
            task_manager.start_task(task_id=task_id, initial_data={"task": initial_text})
            task_manager.update_task_state(task_id, owner, status)
        except Exception:
            pass


def intent_node(state: AgentState):
    """
    Sub-35ms Non-Autoregressive Intent & Complexity Classifier.
    Eliminates Gemini LLM call from intent classification.
    """
    task_id = state["task_id"]
    task_text = state["task_payload"].text_content or ""
    task_manager.start_task(task_id=task_id, initial_data={"task": task_text})
    task_manager.update_task_state(task_id, "intent_classifier", TaskStatus.IN_PROGRESS)
    
    registered_agents = registry.get_all_capabilities().keys()
    worker_candidates = [
        a for a in registered_agents 
        if a not in ["intent_classifier", "planner", "executor", "reviewer"]
    ]

    target_agent, complexity, confidence = laya_engine.route_intent(task_text, worker_candidates)
    logger.info(f"[IntentNode] Decision: target={target_agent}, complexity={complexity}, conf={confidence:.2f}")

    if target_agent not in worker_candidates and target_agent not in ["planner", "fallback"]:
        target_agent = "fallback"

    task_manager.update_task_state(task_id, "intent_classifier", TaskStatus.COMPLETED)
    
    routing_decision = "planner" if complexity == "complex" else target_agent

    return {
        "complexity": complexity, 
        "routing_decision": routing_decision,
        "agent": target_agent,
        "intent": "coding" if target_agent == "coder" else ("research" if target_agent == "researcher" else target_agent),
        "confidence": confidence
    }

def planner_node(state: AgentState):
    """
    Constructs a structured DAG ExecutionPlan with TaskSpecs.
    """
    task_id = state["task_id"]
    safe_update_task_state(task_id, "planner", TaskStatus.IN_PROGRESS, state["task_payload"].text_content or "")
    
    handler = registry.get_agent("planner")
    response = handler(state["task_payload"])
    
    tasks_list: List[Dict[str, Any]] = []
    try:
        raw_plan = json.loads(clean_json(response.content))
        if isinstance(raw_plan, list):
            for idx, item in enumerate(raw_plan):
                tid = item.get("task_id", f"task_{idx+1:02d}")
                agent = item.get("agent", "coder")
                subtask = item.get("subtask") or item.get("task", state["task_payload"].text_content)
                deps = item.get("depends_on", [])
                tasks_list.append(
                    TaskSpec(
                        task_id=tid,
                        agent=agent,
                        subtask=subtask,
                        depends_on=deps,
                        status=SpecTaskStatus.PENDING
                    ).model_dump()
                )
    except Exception as e:
        logger.warning(f"[PlannerNode] Failed to parse plan JSON ({e}). Falling back to single-task DAG.")

    if not tasks_list:
        tasks_list = [
            TaskSpec(
                task_id="task_01",
                agent=state.get("agent", "coder"),
                subtask=state["task_payload"].text_content or "",
                depends_on=[],
                status=SpecTaskStatus.PENDING
            ).model_dump()
        ]

    # Validate cycles using Kahn's algorithm
    task_specs = [TaskSpec(**t) for t in tasks_list]
    if DAGScheduler.detect_cycle(task_specs):
        logger.warning("[PlannerNode] Cycle detected in plan dependencies. Linearizing tasks.")
        for i in range(len(tasks_list)):
            tasks_list[i]["depends_on"] = [tasks_list[i-1]["task_id"]] if i > 0 else []

    safe_update_task_state(task_id, "planner", TaskStatus.COMPLETED)
    return {"plan": tasks_list, "current_step": 0, "completed_steps": []}

def executor_node(state: AgentState):
    """
    Zero-LLM Deterministic DAG Scheduler (<1ms).
    Resolves next ready TaskSpec without LLM overhead.
    """
    task_id = state["task_id"]
    safe_update_task_state(task_id, "executor", TaskStatus.IN_PROGRESS)
    
    plan_dicts = state.get("plan", [])
    tasks = [TaskSpec(**t) for t in plan_dicts]
    
    next_task = DAGScheduler.get_next_task(tasks)
    
    if next_task:
        next_task.status = SpecTaskStatus.IN_PROGRESS
        # Update the task state inside plan
        updated_plan = [t.model_dump() for t in tasks]
        logger.info(f"[DAGExecutor] Next ready subtask: [{next_task.task_id}] -> Agent: [{next_task.agent}]")
        safe_update_task_state(task_id, "executor", TaskStatus.COMPLETED)
        return {
            "routing_decision": next_task.agent,
            "agent": next_task.agent,
            "current_task_id": next_task.task_id,
            "plan": updated_plan
        }
    else:
        # All tasks completed or ready for review
        logger.info("[DAGExecutor] All DAG tasks completed. Routing to Reviewer Quality Gate.")
        safe_update_task_state(task_id, "executor", TaskStatus.COMPLETED)
        return {
            "routing_decision": "reviewer",
            "agent": "reviewer"
        }

def reviewer_node(state: AgentState):
    """
    Agent-Aware Universal Quality Gate.
    Verifies domain profile satisfaction (<35ms with Laya Noul) and manages retries.
    """
    task_id = state["task_id"]
    safe_update_task_state(task_id, "reviewer", TaskStatus.IN_PROGRESS)
    
    completed_steps = state.get("completed_steps", [])
    last_output = ""
    last_agent = state.get("agent", "coder")
    
    if completed_steps:
        last_step = completed_steps[-1]
        last_output = last_step.get("result", "")
        last_agent = last_step.get("agent", last_agent)
    elif state.get("response_payload"):
        last_output = state["response_payload"].content

    review_input = InputData(
        input_type=InputType.TEXT,
        text_content=last_output,
        metadata={"target_agent": last_agent, "goal": state["task_payload"].text_content}
    )

    handler = registry.get_agent("reviewer")
    response = handler(review_input)
    
    try:
        data = json.loads(clean_json(response.content))
        status = data.get("status", "approved")
        feedback = data.get("feedback", "")
    except Exception:
        status = "approved"
        feedback = ""

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    plan_dicts = list(state.get("plan", []))

    if status == "rejected":
        retry_count += 1
        logger.warning(f"[Reviewer] Task rejected on attempt {retry_count}/{max_retries}. Feedback: {feedback}")
        if retry_count >= max_retries:
            logger.error(f"[Reviewer] Exceeded max retries ({max_retries}). Triggering Self-Healing Workspace Rollback (Pillar 9).")
            rolled_back = security_gate.rollback_workspace()
            if rolled_back:
                logger.warning(f"[SecurityGate] Rolled back workspace changes: {rolled_back}")
            safe_update_task_state(task_id, "reviewer", TaskStatus.FAILED)
            return {
                "routing_decision": "fallback",
                "feedback": feedback,
                "retry_count": retry_count
            }
        else:
            # Reopen the failed subtask in the plan and inject feedback
            if plan_dicts:
                last_task_dict = plan_dicts[-1]
                last_task_dict["status"] = SpecTaskStatus.PENDING.value
                last_task_dict["feedback"] = feedback
            safe_update_task_state(task_id, "reviewer", TaskStatus.COMPLETED)
            return {
                "routing_decision": "rejected",
                "feedback": feedback,
                "retry_count": retry_count,
                "plan": plan_dicts
            }

    # Task approved: Commit workspace file changes
    security_gate.commit_workspace()
    safe_update_task_state(task_id, "reviewer", TaskStatus.COMPLETED)
    return {
        "routing_decision": "approved",
        "feedback": feedback,
        "retry_count": retry_count
    }

def create_agent_node(agent_name: str):
    def node_func(state: AgentState):
        task_id = state["task_id"]
        safe_update_task_state(task_id, agent_name, TaskStatus.IN_PROGRESS)
        
        handler = registry.get_agent(agent_name)
        if not handler:
            logger.error(f"Agent [{agent_name}] not found in registry.")
            safe_update_task_state(task_id, agent_name, TaskStatus.FAILED)
            return {"routing_decision": "fallback", "agent": "fallback"}

        # Determine prompt content: subtask-aware vs direct prompt
        plan_dicts = list(state.get("plan", []))
        current_tid = state.get("current_task_id")
        active_task: Optional[Dict[str, Any]] = None

        if state.get("complexity") == "complex" and plan_dicts:
            for t in plan_dicts:
                if t.get("task_id") == current_tid:
                    active_task = t
                    break

        wb: WhiteboardContext = state.get("whiteboard")
        if wb is None:
            wb = WhiteboardContext()

        if active_task:
            subtask_prompt = active_task.get("subtask", state["task_payload"].text_content or "")
            if active_task.get("feedback"):
                subtask_prompt += f"\n\n[REVIEWER CRITIQUE FROM PREVIOUS ATTEMPT]: {active_task['feedback']}\nPlease fix these issues."
            
            # Inject context of upstream dependencies from the Whiteboard
            deps = active_task.get("depends_on", [])
            upstream_artifacts = wb.format_context_for_prompt(deps) if deps else ""
            if upstream_artifacts:
                subtask_prompt += f"\n\n[UPSTREAM ARTIFACTS FROM WHITEBOARD]:\n{upstream_artifacts}"
            else:
                # Fallback to prior completed steps if direct whiteboard artifacts not yet present
                completed = state.get("completed_steps", [])
                if completed:
                    subtask_prompt += f"\n\n[PRIOR COMPLETED ARTIFACTS]:\n" + "\n".join(
                        f"### Agent {c.get('agent')} Output:\n{c.get('result', '')}\n" for c in completed
                    )
            
            worker_payload = InputData(
                input_type=InputType.TEXT,
                text_content=subtask_prompt,
                metadata={"task_id": current_tid, "source": state.get("source", "cli")}
            )
        else:
            worker_payload = state["task_payload"]

        # Call the worker agent
        response = handler(worker_payload)

        # Publish task output artifact to Whiteboard
        tid = active_task.get("task_id", "direct_task") if active_task else "direct_task"
        art_type = "code" if agent_name in ("coder", "devops") else ("json_schema" if agent_name == "designer" else "text")
        wb.publish(
            key=f"{tid}_{agent_name}_output",
            content=response.content,
            author=agent_name,
            task_id=tid,
            artifact_type=art_type
        )

        # Mark active task completed in plan
        completed_steps = list(state.get("completed_steps", []))
        if active_task:
            active_task["status"] = SpecTaskStatus.COMPLETED.value
            active_task["result"] = response.content
            completed_steps.append({
                "task_id": active_task.get("task_id"),
                "agent": agent_name,
                "result": response.content
            })
        else:
            completed_steps.append({
                "task_id": "direct_task",
                "agent": agent_name,
                "result": response.content
            })

        safe_update_task_state(task_id, agent_name, TaskStatus.COMPLETED)
        return {
            "response_payload": response,
            "completed_steps": completed_steps,
            "plan": plan_dicts,
            "whiteboard": wb
        }
    return node_func

def fallback_node(state: AgentState):
    task_id = state["task_id"]
    safe_update_task_state(task_id, "fallback", TaskStatus.FAILED)
    
    fallback_response = AgentResponse(
        agent_id="fallback",
        status=ResponseStatus.FAILURE,
        content="Fallback agent reached due to invalid routing, exceeded retries, or missing capabilities.",
        tool_calls=[],
        error_message="Fallback reached."
    )
    return {
        "routing_decision": "approved",
        "agent": "fallback",
        "response_payload": fallback_response
    }

def route_after_intent(state: AgentState) -> str:
    if state["complexity"] == "complex":
        return "planner"
    if state["agent"] == "fallback":
        return "fallback"
    return state["routing_decision"]

def route_after_executor(state: AgentState) -> str:
    if state["routing_decision"] == "reviewer":
        return "reviewer"
    if state["routing_decision"] == "fallback":
        return "fallback"
    return state["routing_decision"]
    
def aggregator_node(state: AgentState):
    """
    Bottom-Up Multi-Agent Aggregator Node (Pillars 4 & 8).
    Synthesizes outputs from all executed DAG steps into an executive deliverable.
    """
    task_id = state["task_id"]
    safe_update_task_state(task_id, "aggregator", TaskStatus.IN_PROGRESS)

    goal = state["task_payload"].text_content or "Orchestration Goal"
    completed = state.get("completed_steps", [])
    wb = state.get("whiteboard")

    elapsed_ms = (time.time() - state.get("start_time", time.time())) * 1000
    deliverable = format_executive_deliverable(
        user_goal=goal,
        completed_steps=completed,
        whiteboard=wb,
        total_latency_ms=elapsed_ms
    )

    response = AgentResponse(
        agent_id="aggregator",
        status=ResponseStatus.SUCCESS,
        content=deliverable,
        tool_calls=[],
        metadata={"total_completed_steps": len(completed)}
    )

    safe_update_task_state(task_id, "aggregator", TaskStatus.COMPLETED)
    return {
        "response_payload": response,
        "routing_decision": "approved",
        "agent": "aggregator"
    }

def route_after_worker(state: AgentState) -> str:
    if state["complexity"] == "complex":
        return "executor"
    return "reviewer"
    
def route_after_reviewer(state: AgentState) -> str:
    if state["routing_decision"] == "rejected":
        if state["complexity"] == "complex":
            return "executor"
        return state.get("agent", "fallback")
    if state["routing_decision"] == "fallback":
        return "fallback"
    if state.get("complexity") == "complex" and len(state.get("completed_steps", [])) >= 1:
        return "aggregator"
    return END

def create_orchestrator():
    graph = StateGraph(AgentState)

    graph.add_node("intent", intent_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("aggregator", aggregator_node)
    graph.add_node("fallback", fallback_node)
    
    # Add Worker Agents
    registered_agents = registry.get_all_capabilities().keys()
    workers = [a for a in registered_agents if a not in ["intent_classifier", "planner", "executor", "reviewer", "aggregator"]]
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
    
    # Worker routing: always verify output through Reviewer
    for agent_name in workers:
        graph.add_conditional_edges(agent_name, route_after_worker, {"executor": "executor", "reviewer": "reviewer"})
        
    # Reviewer routing: on approval goes to aggregator or END, on rejection retries worker/executor
    rev_targets = {"executor": "executor", "fallback": "fallback", "aggregator": "aggregator", END: END}
    for w in workers:
        rev_targets[w] = w
    graph.add_conditional_edges("reviewer", route_after_reviewer, rev_targets)
    graph.add_edge("aggregator", END)
    graph.add_edge("fallback", END)

    return graph.compile()

def run_orchestrator(
    task_text: str,
    task_id: Optional[str] = None,
    session_id: str = "session-001",
    source: str = "cli",
) -> dict:
    try:
        if task_id is None:
            task_id = f"task-{uuid.uuid4().hex[:8]}"

        orchestrator_key = key_manager.get_api_key_for_role("ORCHESTRATOR")
        if orchestrator_key:
            logger.info("[Orchestrator] Initialized with Gemini API key (GEMINI_API_KEY_ORCHESTRATOR)")
        else:
            logger.warning("[Orchestrator] GEMINI_API_KEY_ORCHESTRATOR is not set; running with resilient fallback")

        app = create_orchestrator()
        
        input_data = InputData(
            input_type=InputType.TEXT,
            text_content=task_text,
            metadata={"source": source}
        )

        initial_state = {
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
            "current_task_id": None,
            "completed_steps": [],
            "feedback": "",
            "retry_count": 0,
            "max_retries": 3,
            "intent": "unknown",
            "confidence": 0.0,
            "whiteboard": WhiteboardContext(),
            "start_time": time.time(),
        }

        result = app.invoke(initial_state)

        # Ensure response_payload is populated even in complex pipeline runs
        if result.get("response_payload") is None and result.get("completed_steps"):
            last_step = result["completed_steps"][-1]
            result["response_payload"] = AgentResponse(
                agent_id=last_step.get("agent", "orchestrator"),
                status=ResponseStatus.SUCCESS,
                content=last_step.get("result", "Tasks completed successfully."),
                tool_calls=[],
                metadata={"plan_length": len(result.get("plan", []))}
            )

        return result

    except Exception:
        logger.exception("Orchestration failed for task_id=%s", task_id)
        raise

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    
    print("="*60)
    print("  Riva-AGI: FULL INTEGRATION RUN (O1, O2, O3, O4)")
    print("="*60)
    
    task = input("\nEnter your task (or press Enter for a dummy test): ").strip()
    if not task:
        task = "Write a python function to compute summary statistics"
    
    print(f"\nUser Request: {task}\n")
    
    result = run_orchestrator(task)

    print("\n" + "="*60)
    print("  FINAL AGENT RESPONSE (O2 SCHEMA)")
    print("="*60)
    if result.get("response_payload"):
        print(result["response_payload"].model_dump_json(indent=2))
    
    print("\n" + "="*60)
    print("  FINAL TASK HISTORY (O3 TRACKER)")
    print("="*60)
    final_history = task_manager.get_task_status(result["task_id"])
    if final_history:
        print(final_history.model_dump_json(indent=2))
