"""Agent registry data models."""

from typing import List
from pydantic import BaseModel, Field


class AgentItem(BaseModel):
    """Schema for a single registered agent."""
    name: str = Field(..., description="Unique agent identifier")
    description: str = Field(..., description="Agent description and capabilities")
    tools: List[str] = Field(default_factory=list, description="List of tools available to this agent")
    level: str = Field("TASK_DOER", description="Hierarchical agent level (CEO, MANAGER, TASK_DOER)")


class AgentsListResponse(BaseModel):
    """Response schema for agent listing."""
    agents: List[AgentItem] = Field(..., description="List of all registered agents in Riva-AGI")
