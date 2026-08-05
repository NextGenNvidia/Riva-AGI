"""Dummy System Agent — orchestration/agents/dummy_system_agent.py
=================================================================
A 3rd dummy agent to test the Registration System (Task O4).
"""
import logging
from orchestration.orchestrator.registry import registry, AgentCapabilities

# Setup standard logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@registry.register(
    name="dummy_system",
    capabilities=AgentCapabilities(
        description="Handles system-level operations.",
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

if __name__ == "__main__":
    logger.info("=== Testing Dummy System Agent Registration ===")
    
    # Confirm registration works
    capabilities = registry.get_all_capabilities()
    if "dummy_system" in capabilities:
        logger.info(f"Capabilities registered successfully:\n{capabilities['dummy_system'].model_dump_json(indent=2)}")
    
    handler = registry.get_agent("dummy_system")
    if handler:
        result = handler("List files in directory")
        logger.info(f"Execution Result: {result}")
