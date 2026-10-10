"""Voice Gateway Service for Riva-AGI.

Bridges browser Web Audio WebSocket connections with the Gemini Live API.
Coordinates SessionManager (concurrency & circuit breaker), ConversationState,
and bidirectional live streaming.
"""

import logging
from typing import Optional, Tuple
from fastapi import WebSocket, WebSocketDisconnect

from voice_speech.engine.config.settings import Settings
from voice_speech.engine.conversation.session_manager import SessionManager
from voice_speech.engine.conversation.state import ConversationState
from voice_speech.engine.gemini.session import create_gemini_client
from voice_speech.engine.gemini.streaming import run_live_bridge
from Backend.config import config

logger = logging.getLogger("riva.backend.voice_service")


class VoiceService:
    """Manages Gemini Live client connections, concurrency, and audio streaming."""

    def __init__(self):
        self.settings = Settings()
        self.session_manager = SessionManager()
        self.gemini_client = None

        if self.settings.gemini.api_key:
            try:
                self.gemini_client = create_gemini_client(api_key=self.settings.gemini.api_key)
                logger.info("Gemini Live client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Live client: {e}")
        else:
            logger.warning(
                "GEMINI_API_KEY is not set for voice service! "
                "Voice streaming endpoints will reject connections until an API key is provided."
            )

    def is_configured(self) -> bool:
        """Returns True if the voice engine has a valid Gemini client configured."""
        return self.gemini_client is not None and bool(self.settings.gemini.api_key)

    def get_status(self) -> dict:
        """Returns current operational status and session metrics."""
        is_circuit_open, cooldown_remaining = self.session_manager.is_circuit_open()
        default_voice = getattr(self.settings.gemini, "voice_name", "Aoede")
        return {
            "status": "ready" if self.is_configured() else "degraded (no api key)",
            "active_sessions": self.session_manager.active_sessions,
            "max_concurrent_sessions": self.session_manager.max_concurrent_sessions,
            "circuit_breaker_open": is_circuit_open,
            "circuit_cooldown_remaining_sec": round(cooldown_remaining, 1),
            "model": self.settings.gemini.model,
            "default_voice": default_voice,
        }

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """Manages a single browser client voice streaming WebSocket session."""
        # 1. Validate Origin
        origin = websocket.headers.get("origin", "")
        if origin and origin not in config.allowed_ws_origins:
            logger.warning(f"Rejected WebSocket from unauthorized origin: {origin}")
            await websocket.close(code=4003, reason="Origin not allowed")
            return

        # 2. Check if API key / client is ready
        if not self.gemini_client:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "Voice service unavailable: GEMINI_API_KEY not configured.",
            })
            await websocket.close(code=4001, reason="API Key Not Configured")
            return

        # 3. Concurrency & Circuit Breaker Admission
        acquired, error_msg = await self.session_manager.try_acquire()
        if not acquired:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": error_msg})
            await websocket.close(code=4029, reason=error_msg)
            return

        try:
            await websocket.accept()
        except Exception:
            await self.session_manager.release()
            return

        voice = websocket.query_params.get("voice") or getattr(self.settings.gemini, "voice_name", "Aoede")
        language = websocket.query_params.get("language") or "auto"
        logger.info(
            f"Browser client connected to /ws (voice={voice}, language={language}) "
            f"[{self.session_manager.active_sessions}/{self.session_manager.max_concurrent_sessions} sessions]"
        )

        state = ConversationState()

        try:
            await run_live_bridge(
                client=self.gemini_client,
                websocket=websocket,
                settings=self.settings,
                state=state,
                session_mgr=self.session_manager,
                voice=voice,
                language=language,
            )
        except WebSocketDisconnect:
            logger.info("Browser client disconnected cleanly from voice WebSocket.")
        except Exception as e:
            logger.error(f"WebSocket voice bridge exception: {e}", exc_info=True)
        finally:
            state.terminate()
            await self.session_manager.release()


# Global singleton instance
voice_service = VoiceService()
