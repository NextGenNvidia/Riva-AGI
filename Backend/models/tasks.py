"""Task state tracking models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStep(BaseModel):
    """Schema for an individual agent execution step within a task."""
    step_id: Optional[str] = None
    agent: str
    status: str
    timestamp: Optional[str] = None
    output: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Schema for task state and execution history."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Overall task status (PENDING, IN_PROGRESS, COMPLETED, FAILED)")
    current_agent: Optional[str] = Field(None, description="Agent currently operating on the task")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Step-by-step agent transitions")
    initial_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Initial task context")
