"""Dummy System Agent — orchestration/agents/dummy_system_agent.py
=================================================================
A 3rd dummy agent to test the Registration System (Task O4).
Includes a simulated orchestrator router to satisfy the O1 dependency check.
"""
import logging
from orchestration.orchestrator.registry import registry, AgentCapabilities

# Setup standard logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@registry.register(
    name="dummy_system",
    capabilities=AgentCapabilities(
        description="Handles system-level operations like reading files or checking memory.",
        tools=["list_files", "check_memory"]
    )
)
def dummy_system_agent(task: str) -> str:
    """
    Executes a system level task.
    Takes <10 lines to add to the system!
    """
    logger.info(f"[Dummy System Agent] Executing task: {task}")
    return f"System Agent completed: {task}"


# ============================================================================
# VERIFICATION SCRIPT (Proving Orchestrator Routing)
# ============================================================================
def dummy_orchestrator_router(task_request: str) -> str:
    """
    Simulates Task O1 (Root Orchestrator).
    Reads the registry, decides which agent fits the task, and routes to it.
    """
    logger.info(f"[Router] Received task: '{task_request}'")
    
    # 1. Read capabilities from registry
    all_capabilities = registry.get_all_capabilities()
    
    # 2. Simple Routing Logic based on keywords
    selected_agent = None
    if "file" in task_request.lower() or "memory" in task_request.lower():
        selected_agent = "dummy_system"
    else:
        selected_agent = "some_other_agent"
        
    # 3. Route to the registered agent
    if selected_agent in all_capabilities:
        logger.info(f"[Router] Decision: Routing to '{selected_agent}' based on capabilities.")
        handler = registry.get_agent(selected_agent)
        if handler:
            return handler(task_request)
    
    return "[Router] Error: No suitable agent registered for this task."


if __name__ == "__main__":
    logger.info("=== Testing Sub-Agent Registration & Routing (Task O4) ===")
    
    # Simulate a user request that requires system operations
    user_request = "Please list all files in the current directory."
    
    # Send it to the Orchestrator Router
    final_result = dummy_orchestrator_router(user_request)
    
    logger.info(f"=== Final Orchestrator Result ===\n{final_result}")
