"""Task State Manager — orchestrator/state_manager.py
======================================================
Tracks multi-step tasks as they route across agents to maintain context.
"""
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Setup standard logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TaskStatus(str, Enum):
    """Enumeration of possible task statuses."""
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskHistoryEntry(BaseModel):
    """Represents a single step in the task's execution history."""
    step: int = Field(..., description="The sequence number of the step.")
    owner: str = Field(..., description="The ID of the agent executing this step.")
    status: TaskStatus = Field(..., description="The status of the task at this step.")

class TaskState(BaseModel):
    """Strictly typed schema representing the current state of a task."""
    task_id: str = Field(..., description="Unique ID for the task.")
    current_step: int = Field(default=1, description="The current execution step number.")
    owner: str = Field(default="orchestrator", description="The agent currently owning the task.")
    status: TaskStatus = Field(default=TaskStatus.IN_PROGRESS, description="Current overall status.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary payload and context data.")
    history: List[TaskHistoryEntry] = Field(default_factory=list, description="Chronological log of agent transitions.")

class TaskStateManager:
    """
    Task State/Queue Manager (Task 3)
    Tracks multi-step tasks as they move across agents to maintain context securely.
    """
    def __init__(self):
        # In-memory dictionary: task_id -> TaskState Pydantic Model
        self._tasks: Dict[str, TaskState] = {}

    def start_task(self, task_id: str, initial_data: Dict[str, Any]) -> None:
        """Initialize a new task with strict Pydantic structures."""
        self._tasks[task_id] = TaskState(
            task_id=task_id,
            current_step=1,
            owner="orchestrator",
            status=TaskStatus.IN_PROGRESS,
            data=initial_data,
            history=[]
        )
        logger.info(f"Task '{task_id}' started.")

    def update_task_state(self, task_id: str, new_owner: str, status: TaskStatus, step_data: Optional[Dict[str, Any]] = None) -> None:
        """Update the current state of a task as it routes to different agents."""
        if task_id not in self._tasks:
            logger.error(f"Failed to update state: Task {task_id} not found.")
            raise ValueError(f"Task {task_id} not found.")
        
        state = self._tasks[task_id]
        
        # Log history
        history_entry = TaskHistoryEntry(
            step=state.current_step,
            owner=state.owner,
            status=state.status
        )
        state.history.append(history_entry)
        logger.debug(f"Task '{task_id}' history logged for step {state.current_step}.")
        
        # Update state
        state.current_step += 1
        state.owner = new_owner
        state.status = status
        
        if step_data is not None:
            state.data.update(step_data)
            
        logger.info(f"Task '{task_id}' transitioned to '{new_owner}' with status '{status.value}'.")

    def get_task_status(self, task_id: str) -> Optional[TaskState]:
        """Query function: 'what's the status of task #X'"""
        return self._tasks.get(task_id)


if __name__ == "__main__":
    # Test with a 3-step dummy task running across 2+ agents
    logger.info("=== Running State Manager Verification ===")
    manager = TaskStateManager()
    
    manager.start_task("task-101", {"input": "Analyze market trends"})
    manager.update_task_state("task-101", new_owner="researcher", status=TaskStatus.PROCESSING)
    manager.update_task_state("task-101", new_owner="coder", status=TaskStatus.PROCESSING, step_data={"research_result": "Trends found..."})
    manager.update_task_state("task-101", new_owner="orchestrator", status=TaskStatus.COMPLETED)
    
    logger.info("--- Final Query of Task #101 Status ---")
    final_status = manager.get_task_status("task-101")
    if final_status:
        print(final_status.model_dump_json(indent=2))
