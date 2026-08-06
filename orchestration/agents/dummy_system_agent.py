"""Dummy System Agent — orchestration/agents/dummy_system_agent.py
=================================================================
A 3rd dummy agent to test the Registration System (Task O4).
Includes a simulated orchestrator router to satisfy the O1 dependency check.
"""
import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus

# Setup standard logger
logger = logging.getLogger(__name__)

@registry.register(
    name="dummy_system",
    capabilities=AgentCapabilities(
        description="Handles system-level operations like reading files or checking memory.",
        tools=["list_files", "check_memory"]
    )
)
def dummy_system_agent(task_data: InputData) -> AgentResponse:
    """
    Executes a system level task.
    Takes <10 lines to add to the system!
    """
    logger.info(f"[Dummy System Agent] Executing task: {task_data.text_content}")
    
    start_time = time.time()
    
    # Process
    content = f"System Agent completed: {task_data.text_content}"
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="dummy_system",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )


# ============================================================================
# VERIFICATION SCRIPT (Proving Orchestrator Routing)
# ============================================================================
def dummy_orchestrator_router(task_request: InputData) -> AgentResponse:
    """
    Simulates Task O1 (Root Orchestrator).
    Reads the registry, decides which agent fits the task, and routes to it.
    """
    text_req = task_request.text_content or ""
    logger.info(f"[Router] Received task: '{text_req}'")
    
    # 1. Read capabilities from registry
    all_capabilities = registry.get_all_capabilities()
    
    # 2. Simple Routing Logic based on keywords
    selected_agent = None
    if "file" in text_req.lower() or "memory" in text_req.lower():
        selected_agent = "dummy_system"
    else:
        selected_agent = "some_other_agent"
        
    # 3. Route to the registered agent
    if selected_agent in all_capabilities:
        logger.info(f"[Router] Decision: Routing to '{selected_agent}' based on capabilities.")
        handler = registry.get_agent(selected_agent)
        if handler:
            return handler(task_request)
    
    return AgentResponse(
        agent_id="router",
        status=ResponseStatus.FAILED,
        content="[Router] Error: No suitable agent registered for this task.",
        tool_calls=[],
        execution_time_ms=0.0
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger.info("=== Testing Sub-Agent Registration & Routing (Task O4) ===")
    
    from orchestration import InputType
    
    # Simulate a user request that requires system operations
    user_request = InputData(
        input_type=InputType.TEXT,
        text_content="Please list all files in the current directory."
    )
    
    # Send it to the Orchestrator Router
    final_result = dummy_orchestrator_router(user_request)
    
    logger.info(f"=== Final Orchestrator Result ===\n{final_result.model_dump_json(indent=2)}")
