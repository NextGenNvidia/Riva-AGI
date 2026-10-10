"""System telemetry and health check models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ServiceStatuses(BaseModel):
    """Health status of each Riva-AGI subsystem."""
    orchestrator: str = Field("ready", description="Multi-agent orchestrator status")
    rag: str = Field("ready", description="RAG knowledge retrieval status")
    mongodb: str = Field("connected", description="MongoDB database connectivity")
    voice: str = Field("ready", description="Voice & speech gateway status")


class HealthResponse(BaseModel):
    """Global system health response."""
    status: str = Field("ok", description="Overall backend health status")
    services: ServiceStatuses = Field(default_factory=ServiceStatuses)
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")


class MetricsResponse(BaseModel):
    """System hardware telemetry response."""
    cpu: Dict[str, Any] = Field(..., description="CPU metrics and core counts")
    memory: Dict[str, Any] = Field(..., description="System RAM usage stats")
    battery: Dict[str, Any] = Field(..., description="Battery metrics and charging status")
    gpu: List[Dict[str, Any]] = Field(default_factory=list, description="GPU hardware stats")
