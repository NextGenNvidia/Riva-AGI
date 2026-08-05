from typing import Callable, Dict, Any, List, Optional

class AgentRegistry:
    """
    Sub-Agent Registration System (Task 4)
    Allows agents to register themselves with their capabilities and tools.
    """
    def __init__(self):
        # name -> { "handler": callable, "capabilities": dict }
        self._agents: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, capabilities: Dict[str, Any]):
        """
        Decorator to register an agent function.
        """
        def decorator(func: Callable):
            self._agents[name] = {
                "handler": func,
                "capabilities": capabilities
            }
            return func
        return decorator

    def get_agent(self, name: str) -> Optional[Callable]:
        """Retrieve an agent's handler function by name."""
        agent_data = self._agents.get(name)
        if agent_data:
            return agent_data["handler"]
        return None

    def get_all_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Return a mapping of all registered agents and their capabilities."""
        return {name: data["capabilities"] for name, data in self._agents.items()}

# Global registry instance to be imported by agents
registry = AgentRegistry()


if __name__ == "__main__":
    # Test registry
    @registry.register("test_agent", {"skills": ["testing"], "tools": []})
    def test_agent_func(task: str):
        return f"Test agent processing: {task}"

    print("Registered Agents:", list(registry.get_all_capabilities().keys()))
    print("Test Agent capabilities:", registry.get_all_capabilities()["test_agent"])
    
    handler = registry.get_agent("test_agent")
    print(handler("Hello World!"))
