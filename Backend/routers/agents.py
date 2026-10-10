"""Agent Registry Router."""

import logging
from typing import List
from fastapi import APIRouter

import orchestration.agents  # noqa: F401 - ensure all agents self-register
from Backend.models.agents import AgentItem, AgentsListResponse
from Backend.services.orchestrator_service import orchestrator_service

logger = logging.getLogger("riva.backend.routers.agents")

router = APIRouter(tags=["Agent Registry"])


@router.get("/list", response_model=AgentsListResponse, summary="List Registered Agents")
async def list_agents() -> AgentsListResponse:
    """Returns a list of all registered agents in Riva-AGI with their tools and hierarchical level."""
    capabilities = orchestrator_service.get_agent_capabilities()
    items: List[AgentItem] = []

    for name, cap in capabilities.items():
        items.append(
            AgentItem(
                name=name,
                description=cap.description,
                tools=cap.tools,
                level=cap.agent_level,
            )
        )

    return AgentsListResponse(agents=items)
