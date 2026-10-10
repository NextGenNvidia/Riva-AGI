"""Voice engine data models."""

from typing import Optional
from pydantic import BaseModel, Field


class VoiceStatusResponse(BaseModel):
    """Schema for voice gateway status reporting."""
    status: str = Field("ready", description="Current voice bridge status")
    active_sessions: int = Field(0, description="Active concurrent WebSocket voice sessions")
    max_concurrent_sessions: int = Field(5, description="Maximum permitted concurrent sessions")
    circuit_breaker_open: bool = Field(False, description="Whether the quota circuit breaker is tripped")
    circuit_cooldown_remaining_sec: float = Field(0.0, description="Remaining seconds on cooldown if open")
    model: str = Field("gemini-3.1-flash-live-preview", description="Gemini Live model in use")
    default_voice: str = Field("Aoede", description="Default Gemini voice personality")
