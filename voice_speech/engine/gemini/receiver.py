"""
Gemini Receiver Task for Riva.
Receives server messages, parses native PCM audio chunks, and triggers instant barge-in.
"""

import asyncio
import logging
from google.genai.live import AsyncSession
from google.genai import types, errors
import websockets.exceptions

from ..audio.playback import AudioPlayback
from ..conversation.state import ConversationState, StateManager
from .session import GeminiSessionManager

logger = logging.getLogger("riva.gemini.receiver")


class GeminiReceiver:
    """Consumes Gemini Live API WebSocket stream."""

    def __init__(
        self,
        session: AsyncSession,
        session_manager: GeminiSessionManager,
        playback: AudioPlayback,
        out_queue: asyncio.Queue,
        state_manager: StateManager,
    ):
        self.session = session
        self.session_manager = session_manager
        self.playback = playback
        self.out_queue = out_queue
        self.state_manager = state_manager
        self._running = False
        self._task: asyncio.Task | None = None
        self._turn_in_progress = False
        self._first_chunk_for_turn = True
        self._current_epoch = 0

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._receive_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _receive_loop(self) -> None:
        """Hot path: receive from socket, push to playback queue, handle barge-in."""
        while self._running:
            try:
                async for response in self.session.receive():
                    if not self._running:
                        break

                    # 1. Handle Session Resumption update
                    if response.session_resumption_update:
                        self.session_manager.update_resumption_handle(
                            response.session_resumption_update.new_handle
                        )

                    # 2. Handle Go Away message for proactive reconnect
                    if response.go_away:
                        self.session_manager.handle_go_away(response.go_away.time_left)

                    # 3. Handle Voice Activity Detection signals
                    if response.voice_activity:
                        self.state_manager.transition_to(ConversationState.USER_SPEAKING)

                    # 4. Instant Barge-In detection
                    if response.server_content and response.server_content.interrupted:
                        logger.info("Model interrupted by user barge-in.")
                        self.playback.handle_barge_in()  # Advances playback epoch & physically flushes DAC
                        self.state_manager.transition_to(ConversationState.BARGE_IN)
                        self._turn_in_progress = False
                        self._first_chunk_for_turn = True
                        # Do NOT advance self._current_epoch here — keeping it at the old epoch
                        # guarantees any in-flight packets from the interrupted turn are tagged with
                        # the old epoch and dropped by playback's epoch guard!
                        continue

                    # 5. Handle Native PCM Audio Output across all parts FIRST
                    pcm_chunks = []
                    if response.data:
                        pcm_chunks.append(response.data)
                    elif response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                pcm_chunks.append(part.inline_data.data)

                    for pcm_data in pcm_chunks:
                        if not self._turn_in_progress:
                            self._turn_in_progress = True
                            self.state_manager.transition_to(ConversationState.MODEL_RESPONDING)

                        if self._first_chunk_for_turn:
                            self._first_chunk_for_turn = False
                            # Synchronize receiver epoch with playback's current epoch for the new turn
                            self._current_epoch = self.playback.current_epoch
                            self.state_manager.transition_to(ConversationState.PLAYING_AUDIO)

                        try:
                            if self.out_queue.full():
                                try:
                                    self.out_queue.get_nowait()
                                    self.out_queue.task_done()
                                except asyncio.QueueEmpty:
                                    pass
                            self.out_queue.put_nowait((self._current_epoch, pcm_data))
                        except Exception as e:
                            logger.error(f"Error queueing playback audio: {e}")

                    # 6. Turn completion
                    if response.server_content and response.server_content.turn_complete:
                        self._turn_in_progress = False
                        self._first_chunk_for_turn = True

                        # If playback has already drained completely, transition to LISTENING
                        if not self.playback.is_playing:
                            self.state_manager.transition_to(ConversationState.LISTENING)

            except asyncio.CancelledError:
                break
            except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosed):
                logger.info("Gemini Live session closed cleanly.")
                break
            except errors.APIError as e:
                if "1000" in str(e):
                    logger.info("Gemini Live session closed cleanly (1000 OK).")
                else:
                    logger.warning(f"Gemini API error: {e}")
                break
            except Exception as e:
                logger.error(f"Error in Gemini receive loop: {e}", exc_info=True)
                self.state_manager.transition_to(ConversationState.ERROR)
                await asyncio.sleep(0.5)
                break
