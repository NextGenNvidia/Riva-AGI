"""Task State Tracking Router."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from Backend.models.tasks import TaskStatusResponse
from Backend.services.orchestrator_service import orchestrator_service

logger = logging.getLogger("riva.backend.routers.tasks")

router = APIRouter(tags=["Task State Tracking"])


@router.get("/{task_id}", response_model=TaskStatusResponse, summary="Get Task Execution Status")
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Polls the status, current agent, and execution step history of a task."""
    state = orchestrator_service.get_task_status(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    return TaskStatusResponse(**state)
