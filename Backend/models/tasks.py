"""Task state tracking models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStep(BaseModel):
    """Schema for an individual agent execution step within a task."""
    step: Optional[int] = Field(None, description="Step sequence number")
    owner: Optional[str] = Field(None, description="Agent executing this step")
    status: Optional[str] = Field(None, description="Status of the task at this step")


class TaskStatusResponse(BaseModel):
    """Schema for task state and execution history."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Overall task status (in_progress, processing, completed, failed)")
    current_step: int = Field(default=1, description="Current execution step sequence number")
    owner: str = Field(default="orchestrator", description="Agent currently owning or executing the task")
    data: Dict[str, Any] = Field(default_factory=dict, description="Task payload and state data")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Step-by-step agent transitions")
