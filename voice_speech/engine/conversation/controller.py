"""
Conversation Controller for Riva.
Coordinates AudioCapture, AudioPlayback, GeminiSessionManager, Sender, and Receiver.
Supports adaptive earphone full-duplex and speaker gating modes.
"""

import asyncio
import logging
from typing import Optional

from ..config.settings import Settings
from ..conversation.state import ConversationState, StateManager
from ..audio.capture import AudioCapture
from ..audio.playback import AudioPlayback
from ..audio.device_mode import detect_output_mode
from ..gemini.session import GeminiSessionManager
from ..gemini.sender import GeminiSender
from ..gemini.receiver import GeminiReceiver

logger = logging.getLogger("riva.controller")


class RivaController:
    """Master controller managing the persistent voice session."""

    def __init__(self, settings: Settings, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.settings = settings
        try:
            self.loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            self.loop = loop or asyncio.new_event_loop()

        # Core state
        self.state_manager = StateManager(ConversationState.DISCONNECTED)

        # Hot-path thread-safe queues
        self.mic_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=3)
        self.out_queue: asyncio.Queue = asyncio.Queue(maxsize=self.settings.audio_out.max_queue_size)

        # Determine audio mode
        output_mode = self.settings.audio_in.output_mode
        if output_mode == "auto":
            output_mode = detect_output_mode()
        logger.info(f"RivaController starting in audio mode: {output_mode}")

        # Playback callbacks
        def on_playback_start():
            self.state_manager.transition_to(ConversationState.PLAYING_AUDIO)

        def on_playback_end():
            if self.state_manager.current_state == ConversationState.BARGE_IN:
                self.state_manager.transition_to(ConversationState.USER_SPEAKING)
            elif self.state_manager.current_state in (ConversationState.PLAYING_AUDIO, ConversationState.MODEL_RESPONDING):
                self.state_manager.transition_to(ConversationState.LISTENING)

        # Subsystems
        self.audio_playback = AudioPlayback(
            config=self.settings.audio_out,
            out_queue=self.out_queue,
            loop=self.loop,
            on_playback_start=on_playback_start,
            on_playback_end=on_playback_end,
        )
        self.audio_capture = AudioCapture(
            config=self.settings.audio_in,
            mic_queue=self.mic_queue,
            loop=self.loop,
            playback=self.audio_playback,
            state_manager=self.state_manager,
            output_mode=output_mode,
        )
        self.session_manager = GeminiSessionManager(
            settings=self.settings,
            state_manager=self.state_manager,
        )

        self._sender_ready = asyncio.Event()
        self._running = False
        self._sender: Optional[GeminiSender] = None
        self._receiver: Optional[GeminiReceiver] = None
        self._main_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start Riva voice assistant session."""
        if self._running:
            return
        self._running = True
        self.audio_playback.start()
        self._main_task = asyncio.create_task(self._session_loop())

        # Block mic capture until sender is actively connected and draining
        await self._sender_ready.wait()
        self.audio_capture.start()

    async def stop(self) -> None:
        """Gracefully stop all subsystems."""
        self._running = False
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
            self._main_task = None

        if self._sender:
            await self._sender.stop()
            self._sender = None
        if self._receiver:
            await self._receiver.stop()
            self._receiver = None

        self.audio_capture.stop()
        self.audio_playback.stop()
        self.state_manager.transition_to(ConversationState.DISCONNECTED)

    async def _session_loop(self) -> None:
        """Manages persistent session lifecycle with auto-reconnection on server go_away or socket drops."""
        while self._running:
            try:
                self.state_manager.transition_to(ConversationState.CONNECTING)
                connect_config = self.session_manager.build_connect_config()

                logger.info(f"Connecting to Gemini Live ({self.settings.gemini.model})...")
                async with self.session_manager.client.aio.live.connect(
                    model=self.settings.gemini.model,
                    config=connect_config,
                ) as session:
                    self.state_manager.transition_to(ConversationState.CONNECTED)
                    self.state_manager.transition_to(ConversationState.LISTENING)
                    logger.info("Riva connected and actively listening.")

                    # Drain any stale mic frames before streaming starts
                    while not self.mic_queue.empty():
                        try:
                            self.mic_queue.get_nowait()
                        except (asyncio.QueueEmpty, ValueError):
                            break

                    # Start streaming tasks
                    self._sender = GeminiSender(
                        session=session,
                        mic_queue=self.mic_queue,
                        input_config=self.settings.audio_in,
                        state_manager=self.state_manager,
                    )
                    self._receiver = GeminiReceiver(
                        session=session,
                        session_manager=self.session_manager,
                        playback=self.audio_playback,
                        out_queue=self.out_queue,
                        state_manager=self.state_manager,
                    )

                    await self._sender.start()
                    await self._receiver.start()
                    self._sender_ready.set()

                    # Wait until server go_away triggered or socket disconnects
                    while self._running:
                        if self.session_manager.reconnect_event.is_set():
                            logger.info("Reconnecting on server signal...")
                            self.session_manager.reconnect_event.clear()
                            break
                        if self._receiver and (self._receiver._task is None or self._receiver._task.done()):
                            break
                        await asyncio.sleep(0.05)

                    if self._sender:
                        await self._sender.stop()
                    if self._receiver:
                        await self._receiver.stop()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Session error: {e}. Reconnecting in 1s...")
                await asyncio.sleep(1.0)
