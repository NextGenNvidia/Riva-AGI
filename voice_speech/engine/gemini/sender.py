"""
Audio Sender Task for Riva.
Continuously drains 20ms mic frames from asyncio.Queue and streams directly to Gemini Live API WebSocket.
Includes robust error handling and guaranteed queue task completion.
"""

import asyncio
import logging
from typing import Optional, Any
from google.genai import types, errors
from google.genai.live import AsyncSession
import websockets.exceptions

from ..config.settings import AudioInputConfig

logger = logging.getLogger("riva.gemini.sender")


class GeminiSender:
    """Streams live microphone frames directly over WebSocket to Gemini Live API."""

    def __init__(
        self,
        session: AsyncSession,
        mic_queue: asyncio.Queue[bytes],
        input_config: AudioInputConfig,
        state_manager: Optional[Any] = None,
    ):
        self.session = session
        self.mic_queue = mic_queue
        self.input_config = input_config
        self.state_manager = state_manager
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._send_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _send_loop(self) -> None:
        """Hot path: pull frame from queue and transmit immediately."""
        mime_type = self.input_config.mime_type
        while self._running:
            try:
                try:
                    frame_bytes = await asyncio.wait_for(self.mic_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue

                try:
                    if frame_bytes:
                        blob = types.Blob(data=frame_bytes, mime_type=mime_type)
                        await self.session.send_realtime_input(audio=blob)
                finally:
                    self.mic_queue.task_done()

            except asyncio.CancelledError:
                break
            except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosed):
                break
            except errors.APIError as e:
                # Check for clean normal closure (code 1000)
                code = getattr(e, "code", None)
                if code == 1000 or "1000" in str(e):
                    logger.debug("Gemini Live session closed cleanly (1000 OK).")
                else:
                    logger.debug(f"Sender API note: {e}")
                break
            except Exception as e:
                logger.error(f"Error sending audio frame to Gemini: {e}")
                await asyncio.sleep(0.01)
