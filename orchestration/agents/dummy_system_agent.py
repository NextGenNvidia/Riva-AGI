from orchestration.orchestrator.registry import registry

@registry.register(
    name="dummy_system",
    capabilities={
        "description": "Handles system-level operations.",
        "tools": ["list_files", "check_memory"]
    }
)
def dummy_system_agent(task: str) -> str:
    """
    A 3rd dummy agent to test the registration system (Task 4)
    Takes <10 lines to add to the system!
    """
    print(f"[Dummy System Agent] Executing task: {task}")
    return f"System Agent completed: {task}"

if __name__ == "__main__":
    # Test to confirm registration works
    print("Capabilities registered:", registry.get_all_capabilities())
    
    handler = registry.get_agent("dummy_system")
    result = handler("List files in directory")
    print("Result:", result)
