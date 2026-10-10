"""Voice Router for Real-Time Bidirectional Audio Streaming.

Provides the primary WebSocket audio bridge (/ws) and status endpoint,
connecting browser Web Audio to the Gemini Live API via VoiceService.
"""

import logging
from fastapi import APIRouter, WebSocket
from Backend.services.voice_service import voice_service
from Backend.models.voice import VoiceStatusResponse

logger = logging.getLogger("riva.backend.routers.voice")

router = APIRouter(tags=["Voice & Speech Gateway"])


@router.websocket("/ws")
async def audio_websocket_endpoint(websocket: WebSocket) -> None:
    """Real-Time Bidirectional Voice WebSocket Endpoint.

    Streams PCM16 audio between browser Web Audio Worklet and Google Gemini Live API.
    Handles rate-limiting, circuit breaker admission, and automatic session resumption.
    """
    await voice_service.handle_websocket(websocket)


@router.get("/api/voice/status", response_model=VoiceStatusResponse, summary="Voice Gateway Status")
async def get_voice_status() -> VoiceStatusResponse:
    """Returns the current operational status, active sessions, and circuit breaker health."""
    status_dict = voice_service.get_status()
    return VoiceStatusResponse(**status_dict)
