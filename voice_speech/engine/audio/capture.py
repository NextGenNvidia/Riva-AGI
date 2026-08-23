"""
Audio Capture Module for Riva.
Captures continuous 20ms frames at 16kHz mono via non-blocking sounddevice callback
and streams raw PCM directly into asyncio.Queue for Gemini Live WebSocket transmission.

Output Modes:
  1. EARPHONES / HEADSET MODE (Full-Duplex):
     - Unmuted, phase-continuous simultaneous streaming.
     - Natural interruption / barge-in.
  2. BUILT-IN SPEAKER MODE (Half-Duplex Guard):
     - Mic frames are gated while audio is actively leaving the DAC (is_actually_playing_audio).
     - Cleanly completes full answer without laptop speaker acoustic bleed self-interruption.
     - Automatically active for new user questions the instant playback stops.
"""

import asyncio
import logging
from typing import Optional, Any
import numpy as np
import sounddevice as sd

from ..config.settings import AudioInputConfig
from .device_mode import detect_output_mode

logger = logging.getLogger("riva.audio.capture")


class AudioCapture:
    """Streams raw microphone PCM directly to asyncio queue with adaptive earphone/speaker mode handling."""

    def __init__(
        self,
        config: AudioInputConfig,
        mic_queue: asyncio.Queue[bytes],
        loop: asyncio.AbstractEventLoop,
        playback: Optional[Any] = None,
        state_manager: Optional[Any] = None,
        output_mode: str = "auto",
    ):
        self.config = config
        self.mic_queue = mic_queue
        self.loop = loop
        self.playback = playback
        self.state_manager = state_manager

        # Resolve output mode ('earphones' vs 'speaker')
        if output_mode == "auto":
            self.output_mode = detect_output_mode()
        else:
            self.output_mode = output_mode.lower()

        logger.info(f"AudioCapture initialized in mode: {self.output_mode}")

        self._stream: Optional[sd.RawInputStream] = None
        self._is_running = False

        # Diagnostics & telemetry
        self._frames_dropped = 0
        self._frames_forwarded_normal = 0

    def refresh_output_mode(self) -> str:
        """Re-check whether earphones or laptop speakers are currently active."""
        if self.config.output_mode == "auto":
            self.output_mode = detect_output_mode()
        else:
            self.output_mode = self.config.output_mode.lower()
        return self.output_mode

    def _audio_callback(self, indata, frames, time_info, status):
        """PortAudio native thread callback (called every 20ms)."""
        if status:
            logger.warning(f"Audio capture status: {status}")

        if not self._is_running:
            return

        raw_bytes = bytes(indata)

        # ── 1. Earphones / Headset Mode (Full-Duplex) ──
        if self.output_mode in ("earphones", "headset", "headphones"):
            self._frames_forwarded_normal += 1
            self.loop.call_soon_threadsafe(self._enqueue_frame, raw_bytes)
            return

        # ── 2. Built-in Speaker Mode (Gated While DAC is Outputting Audio) ──
        if self.playback and self.playback.is_actually_playing_audio:
            self._frames_dropped += 1
            return

        self._frames_forwarded_normal += 1
        self.loop.call_soon_threadsafe(self._enqueue_frame, raw_bytes)

    def _enqueue_frame(self, raw_bytes: bytes) -> None:
        """Thread-safe enqueue into asyncio queue with queue-size overflow protection."""
        if not self._is_running:
            return

        if self.mic_queue.full():
            try:
                self.mic_queue.get_nowait()
                self.mic_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                pass

        try:
            self.mic_queue.put_nowait(raw_bytes)
        except asyncio.QueueFull:
            pass

    def start(self) -> None:
        """Start non-blocking microphone stream."""
        if self._is_running:
            return

        self._is_running = True
        self.refresh_output_mode()

        self._stream = sd.RawInputStream(
            samplerate=self.config.sample_rate,
            blocksize=self.config.samples_per_frame,
            device=self.config.device_index,
            channels=self.config.channels,
            dtype=self.config.dtype,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info(f"AudioCapture started (16kHz RawInputStream active, mode={self.output_mode}).")

    def stop(self) -> None:
        """Stop microphone stream and drain stale frames."""
        if not self._is_running:
            return

        self._is_running = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug(f"Error closing capture stream: {e}")
            self._stream = None

        while not self.mic_queue.empty():
            try:
                self.mic_queue.get_nowait()
                self.mic_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

        logger.info("AudioCapture stopped.")
