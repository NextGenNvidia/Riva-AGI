"""
base.py — Abstract TTSBackend interface.

Every concrete backend (OpenAI, Cartesia, ElevenLabs, Piper, ...) must
subclass TTSBackend and implement at minimum:

    * synthesize()   — return full audio bytes
    * stream()       — yield audio chunks as they arrive
    * is_available() — return False if prerequisites are missing

The router calls is_available() before selecting a backend so the caller
never has to handle ImportError or missing-binary errors mid-synthesis.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class TTSBackend(ABC):
    """Abstract base class for all TTS backends."""

    # -----------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in logs and routing decisions."""

    @property
    def supports_cloning(self) -> bool:
        """True if this backend supports voice cloning. Default: False."""
        return False

    # -----------------------------------------------------------------
    # Availability check
    # -----------------------------------------------------------------

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if the backend can be used right now.

        For API backends: check that an API key is configured AND the SDK
        is installed. For local backends: check that the required binary
        and model file exist. The check must be cheap (no network calls).
        """

    # -----------------------------------------------------------------
    # Synthesis
    # -----------------------------------------------------------------

    @abstractmethod
    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        """
        Synthesize *text* and return the complete audio as bytes (WAV/MP3).

        Parameters
        ----------
        text : str
            The text to synthesize. Must be non-empty.
        voice_id : str | None
            Backend-specific voice identifier. If None, the backend uses
            its configured default voice.

        Returns
        -------
        bytes
            Raw audio bytes. Format depends on the backend (typically MP3
            or WAV). Callers should use player.play_audio() which handles
            both formats.
        """

    @abstractmethod
    def stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        """
        Synthesize *text* and yield audio chunks as they become available.

        The first non-empty chunk arriving signals time-to-first-audio
        (TTFA). Callers can start playback immediately without waiting for
        the full response.

        Parameters
        ----------
        text : str
            The text to synthesize.
        voice_id : str | None
            Backend-specific voice identifier.

        Yields
        ------
        bytes
            Raw audio chunk. May be empty bytes (heartbeat/keepalive);
            callers should skip zero-length chunks.
        """

    # -----------------------------------------------------------------
    # Cost estimation
    # -----------------------------------------------------------------

    def estimate_cost(self, text: str) -> float:
        """
        Return an estimated cost in USD for synthesizing *text*.

        Default implementation returns 0.0 (used by local backends).
        API backends should override this with their per-character rate.
        """
        return 0.0

    # -----------------------------------------------------------------
    # Repr
    # -----------------------------------------------------------------

    def __repr__(self) -> str:
        available = "available" if self.is_available() else "unavailable"
        return f"<{self.__class__.__name__} name={self.name!r} {available}>"
