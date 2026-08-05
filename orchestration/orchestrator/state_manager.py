from typing import Dict, Any, Optional

class TaskStateManager:
    """
    Task State/Queue Manager (Task 3)
    Tracks multi-step tasks as they move across agents to maintain context.
    """
    def __init__(self):
        # In-memory dictionary: task_id -> state
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def start_task(self, task_id: str, initial_data: Any) -> None:
        """Initialize a new task."""
        self._tasks[task_id] = {
            "current_step": 1,
            "owner": "orchestrator",
            "status": "in_progress",
            "data": initial_data,
            "history": []
        }

    def update_task_state(self, task_id: str, new_owner: str, status: str, step_data: Any = None) -> None:
        """Update the current state of a task as it routes to different agents."""
        if task_id not in self._tasks:
            raise ValueError(f"Task {task_id} not found.")
        
        state = self._tasks[task_id]
        
        # Log history
        state["history"].append({
            "step": state["current_step"],
            "owner": state["owner"],
            "status": state["status"]
        })
        
        # Update state
        state["current_step"] += 1
        state["owner"] = new_owner
        state["status"] = status
        
        if step_data is not None:
            if isinstance(state["data"], dict) and isinstance(step_data, dict):
                state["data"].update(step_data)
            else:
                state["data"] = step_data

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Query function: 'what's the status of task #X'"""
        return self._tasks.get(task_id)


if __name__ == "__main__":
    # Test with a 3-step dummy task running across 2+ agents
    manager = TaskStateManager()
    
    print("1. Starting Task...")
    manager.start_task("task-101", {"input": "Analyze market trends"})
    
    print("2. Routing to Researcher...")
    manager.update_task_state("task-101", new_owner="researcher", status="processing")
    
    print("3. Routing to Coder (after researcher finishes)...")
    manager.update_task_state("task-101", new_owner="coder", status="processing", step_data={"research_result": "Trends found..."})
    
    print("4. Finalizing Task...")
    manager.update_task_state("task-101", new_owner="orchestrator", status="completed")
    
    print("\n--- Final Query of Task #101 Status ---")
    status = manager.get_task_status("task-101")
    import json
    print(json.dumps(status, indent=2))
