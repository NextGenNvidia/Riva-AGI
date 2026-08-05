"""Agent Registry — orchestrator/registry.py
===========================================
Allows agents to securely register themselves with their capabilities and tools.
"""
import logging
from typing import Callable, Dict, Any, Optional, List
from pydantic import BaseModel, Field

# Setup standard logger
logger = logging.getLogger(__name__)

class AgentCapabilities(BaseModel):
    """Strictly typed capabilities exposed by a registered agent."""
    description: str = Field(..., description="A short description of what the agent does.")
    tools: List[str] = Field(default_factory=list, description="A list of tool names the agent can execute.")

class AgentRegistry:
    """
    Sub-Agent Registration System (Task 4)
    Maintains a mapping of agent names to their capabilities and execution handlers.
    """
    def __init__(self):
        # name -> { "handler": callable, "capabilities": AgentCapabilities }
        self._agents: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, capabilities: AgentCapabilities):
        """
        Decorator to register an agent function with Pydantic validated capabilities.
        """
        if not isinstance(capabilities, AgentCapabilities):
            capabilities = AgentCapabilities.model_validate(capabilities)
        def decorator(func: Callable):
            self._agents[name] = {
                "handler": func,
                "capabilities": capabilities
            }
            logger.info(f"Agent '{name}' successfully registered with capabilities: {capabilities.model_dump_json()}")
            return func
        return decorator

    def get_agent(self, name: str) -> Optional[Callable]:
        """Retrieve an agent's handler function by name."""
        agent_data = self._agents.get(name)
        if agent_data:
            return agent_data["handler"]
        logger.warning(f"Attempted to retrieve unregistered agent: {name}")
        return None

    def get_all_capabilities(self) -> Dict[str, AgentCapabilities]:
        """Return a mapping of all registered agents and their capabilities."""
        return {name: data["capabilities"] for name, data in self._agents.items()}

# Global registry instance to be imported by agents
registry = AgentRegistry()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger.info("=== Running Registry Verification ===")
    
    # Test registry
    @registry.register("test_agent", AgentCapabilities(description="A test agent", tools=["testing"]))
    def test_agent_func(task: str):
        return f"Test agent processing: {task}"

    logger.info(f"Registered Agents: {list(registry.get_all_capabilities().keys())}")
    logger.info(f"Test Agent capabilities:\n{registry.get_all_capabilities()['test_agent'].model_dump_json(indent=2)}")
    
    handler = registry.get_agent("test_agent")
    if handler:
        logger.info(f"Execution Result: {handler('Hello World!')}")
