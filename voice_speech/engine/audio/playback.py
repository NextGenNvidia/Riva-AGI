"""
Audio Playback Module for Riva.
Handles ultra-low-latency 24kHz audio output using non-blocking sounddevice callback
with epoch-based interruption flushing for sub-15ms physical barge-in silencing.
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Callable
import numpy as np
import sounddevice as sd

from ..config.settings import AudioOutputConfig

logger = logging.getLogger("riva.audio.playback")


class AudioPlayback:
    """Non-blocking 24kHz PortAudio playback DAC with instant barge-in flushing."""

    def __init__(
        self,
        config: AudioOutputConfig,
        out_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
        on_playback_start: Optional[Callable[[], None]] = None,
        on_playback_end: Optional[Callable[[], None]] = None,
    ):
        self.config = config
        self.out_queue = out_queue
        self.loop = loop
        self.on_playback_start = on_playback_start
        self.on_playback_end = on_playback_end

        self._stream: Optional[sd.RawOutputStream] = None
        self._buffer = bytearray()
        self._buffer_lock = threading.Lock()
        self._is_running = False
        self._current_epoch: int = 0
        self._playback_in_progress = False
        self._last_playback_time: float = 0.0
        self._last_playing_rms: float = 0.0
        self._worker_task: Optional[asyncio.Task] = None
        self._barge_in_timestamp_ns: Optional[int] = None

        # Playback timing thresholds
        self.PLAYBACK_SILENCE_RMS = 20.0
        self.SPEAKER_TAIL_MS = 600

        self._speaker_active_until: float = 0.0
        self._last_audio_written_time: float = 0.0

    @property
    def current_epoch(self) -> int:
        return self._current_epoch

    @property
    def is_playing(self) -> bool:
        """Returns true if speaker is actively outputting audio."""
        with self._buffer_lock:
            buf_len = len(self._buffer)
        return buf_len > 0 or self._playback_in_progress or not self.out_queue.empty()

    @property
    def is_actually_playing_audio(self) -> bool:
        """True only when real (non-silent) audio is currently leaving the DAC this instant."""
        return self._last_playing_rms >= self.PLAYBACK_SILENCE_RMS

    @property
    def is_speaker_active(self) -> bool:
        """Debounced — stays True through inter-chunk gaps and conversational pauses for UI/turn state."""
        return time.monotonic() < self._speaker_active_until

    @property
    def last_playing_rms(self) -> float:
        """Returns the real-time RMS energy of audio actively leaving the speaker DAC."""
        return self._last_playing_rms if self.is_playing else 0.0

    def reset_state(self) -> None:
        """Reset internal playback buffers and active flags."""
        with self._buffer_lock:
            self._buffer.clear()
        self._playback_in_progress = False
        self._last_playback_time = 0.0
        self._last_playing_rms = 0.0
        self._last_audio_written_time = 0.0
        self._speaker_active_until = 0.0
        while not self.out_queue.empty():
            try:
                self.out_queue.get_nowait()
                self.out_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

    def _audio_callback(self, outdata, frames, time_info, status):
        """PortAudio native thread callback requesting raw PCM bytes for playback."""
        if status:
            logger.debug(f"Audio playback status: {status}")

        bytes_needed = frames * 2  # 16-bit mono = 2 bytes per sample

        with self._buffer_lock:
            buf_len = len(self._buffer)
            if buf_len >= bytes_needed:
                chunk = bytes(self._buffer[:bytes_needed])
                del self._buffer[:bytes_needed]
                outdata[:] = chunk
                now = time.monotonic()
                self._last_playback_time = now
                self._last_audio_written_time = now
                self._speaker_active_until = now + (self.SPEAKER_TAIL_MS / 1000.0)

                samples = np.frombuffer(chunk, dtype=np.int16)
                self._last_playing_rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

                if not self._playback_in_progress:
                    self._playback_in_progress = True
                    if self.on_playback_start:
                        self.loop.call_soon_threadsafe(self.on_playback_start)

            elif buf_len > 0:
                available = buf_len
                dac_chunk = bytearray(bytes_needed)
                dac_chunk[:available] = self._buffer
                outdata[:] = dac_chunk
                self._buffer.clear()
                now = time.monotonic()
                self._last_playback_time = now
                self._last_audio_written_time = now
                self._speaker_active_until = now + (self.SPEAKER_TAIL_MS / 1000.0)

                samples = np.frombuffer(dac_chunk, dtype=np.int16)
                self._last_playing_rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

                if not self._playback_in_progress:
                    self._playback_in_progress = True
                    if self.on_playback_start:
                        self.loop.call_soon_threadsafe(self.on_playback_start)
            else:
                # Underrun / Silence
                outdata[:] = b"\x00" * bytes_needed
                self._last_playing_rms = 0.0

                if self._barge_in_timestamp_ns is not None:
                    stop_latency_ms = (time.monotonic_ns() - self._barge_in_timestamp_ns) / 1_000_000.0
                    logger.info(f"Barge-in: speaker output physically silenced in {stop_latency_ms:.2f}ms")
                    self._barge_in_timestamp_ns = None

        if self._playback_in_progress and (time.monotonic() - self._last_playback_time > 0.05):
            self._playback_in_progress = False
            if self.on_playback_end:
                self.loop.call_soon_threadsafe(self.on_playback_end)

    async def _queue_drainer(self):
        """Asynchronous worker that continuously moves incoming 24kHz PCM chunks into DAC ring buffer."""
        while self._is_running:
            try:
                try:
                    epoch, chunk = await asyncio.wait_for(self.out_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                try:
                    if epoch < self._current_epoch:
                        continue  # Drop stale in-flight packets from prior interrupted turn

                    with self._buffer_lock:
                        self._buffer.extend(chunk)
                finally:
                    self.out_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in playback queue drainer: {e}")

    def handle_barge_in(self) -> None:
        """Instantly flush all buffers and advance epoch upon barge-in interruption."""
        self._barge_in_timestamp_ns = time.monotonic_ns()
        self._current_epoch += 1

        with self._buffer_lock:
            self._buffer.clear()

        while not self.out_queue.empty():
            try:
                self.out_queue.get_nowait()
                self.out_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

        self._playback_in_progress = False
        self._last_playing_rms = 0.0
        self._speaker_active_until = 0.0

    def start(self) -> None:
        """Start audio playback stream and worker task."""
        if self._is_running:
            return

        self._is_running = True
        self.reset_state()
        self._worker_task = asyncio.create_task(self._queue_drainer())

        self._stream = sd.RawOutputStream(
            samplerate=self.config.sample_rate,
            blocksize=self.config.blocksize,
            device=self.config.device_index,
            channels=self.config.channels,
            dtype=self.config.dtype,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("AudioPlayback started (24kHz RawOutputStream active).")

    def stop(self) -> None:
        """Stop audio playback stream and worker task."""
        if not self._is_running:
            return

        self._is_running = False

        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug(f"Error closing playback stream: {e}")
            self._stream = None

        self.reset_state()
        logger.info("AudioPlayback stopped.")
