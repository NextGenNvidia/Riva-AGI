"""
Gemini Live Session Manager for Riva.
Handles persistent connection, session resumption handles, and go_away proactive reconnection.
"""

import asyncio
import logging
from typing import Optional
from google import genai
from google.genai import types

from ..config.settings import Settings
from ..conversation.state import ConversationState, StateManager

logger = logging.getLogger("riva.gemini.session")


class GeminiSessionManager:
    """Manages persistent WebSocket connection with Gemini Live API."""

    def __init__(self, settings: Settings, state_manager: StateManager):
        self.settings = settings
        self.state_manager = state_manager
        self.client = genai.Client(api_key=self.settings.gemini.api_key)
        self.resumption_handle: Optional[str] = None
        self.active_session: Optional[genai.live.AsyncSession] = None
        self.reconnect_event = asyncio.Event()

    def build_connect_config(self) -> types.LiveConnectConfig:
        """Create the optimized low-latency LiveConnectConfig."""
        vad_config = types.AutomaticActivityDetection(
            disabled=self.settings.vad.disabled,
            start_of_speech_sensitivity=getattr(
                types.StartSensitivity,
                self.settings.vad.start_sensitivity,
                types.StartSensitivity.START_SENSITIVITY_LOW,
            ),
            end_of_speech_sensitivity=getattr(
                types.EndSensitivity,
                self.settings.vad.end_sensitivity,
                types.EndSensitivity.END_SENSITIVITY_HIGH,
            ),
            prefix_padding_ms=self.settings.vad.prefix_padding_ms,
            silence_duration_ms=self.settings.vad.silence_duration_ms,
        )

        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=self.settings.gemini.voice_name
                )
            )
        )

        thinking_level = getattr(
            types.ThinkingLevel,
            self.settings.gemini.thinking_level,
            types.ThinkingLevel.MINIMAL,
        )

        session_resumption = (
            types.SessionResumptionConfig(handle=self.resumption_handle)
            if self.resumption_handle
            else None
        )

        return types.LiveConnectConfig(
            response_modalities=self.settings.gemini.response_modalities,
            speech_config=speech_config,
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=self.settings.gemini.system_instruction)]
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=vad_config
            ),
            session_resumption=session_resumption,
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            ),
        )

    def update_resumption_handle(self, new_handle: Optional[str]) -> None:
        """Save resumption handle for rapid, state-preserving reconnection."""
        if new_handle:
            self.resumption_handle = new_handle
            logger.debug(f"Saved session resumption handle: {new_handle[:16]}...")

    def handle_go_away(self, time_left: Optional[str]) -> None:
        """Proactively prepare for session reconnection before server termination."""
        logger.warning(f"Received go_away from Gemini server (time left: {time_left}). Triggering proactive resumption.")
        self.state_manager.transition_to(ConversationState.SESSION_RESUMING)
        self.reconnect_event.set()
