"""System Telemetry and Health Check Router."""

import datetime
import logging
from fastapi import APIRouter

from Backend.models.system import HealthResponse, MetricsResponse, ServiceStatuses
from Backend.services.system_service import system_service
from Backend.services.voice_service import voice_service
from Backend.services.rag_service import rag_service

logger = logging.getLogger("riva.backend.routers.system")

router = APIRouter(tags=["System & Metrics"])


@router.get("/health", response_model=HealthResponse, summary="System Health Check")
async def health_check() -> HealthResponse:
    """Tells the frontend and monitoring systems if the backend and each subsystem is healthy."""
    rag_health = rag_service.get_health_status()
    voice_status = voice_service.get_status().get("status", "ready")

    return HealthResponse(
        status="ok",
        services=ServiceStatuses(
            orchestrator="ready",
            rag=rag_health.get("rag", "ready"),
            mongodb=rag_health.get("mongodb", "disconnected"),
            voice=voice_status,
        ),
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


@router.get("/metrics", response_model=MetricsResponse, summary="Hardware System Telemetry")
async def system_metrics() -> MetricsResponse:
    """Provides real-time CPU, RAM, Battery, and GPU metrics for system dashboards."""
    metrics_data = await system_service.get_all_metrics()
    return MetricsResponse(**metrics_data)
