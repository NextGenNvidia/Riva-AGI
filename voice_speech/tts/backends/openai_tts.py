"""
backends/openai_tts.py — OpenAI TTS backend (default API engine).

Evaluation summary (Task V2)
-----------------------------
Model     : tts-1 (default) or tts-1-hd (opt-in via OPENAI_TTS_MODEL)
Quality   : 3.8 / 5  (tts-1),  4.3 / 5 (tts-1-hd)
TTFA      : ~500 ms p50  (tts-1)
Streaming : yes — response.iter_bytes()
Cost      : $15 / 1M chars (tts-1),  $30 / 1M chars (tts-1-hd)
Cloning   : no
License   : commercial — standard OpenAI API ToS

Routing role
------------
DEFAULT path when no special context flag is set.
Fallback from Cartesia and ElevenLabs when those backends are unavailable.

References
----------
https://platform.openai.com/docs/guides/text-to-speech
"""

from __future__ import annotations

import logging
from typing import Iterator

try:
    from voice_speech.tts.backends.base import TTSBackend
    from voice_speech.tts.config import BackendConfig
except ImportError:
    from backends.base import TTSBackend
    from config import BackendConfig

_log = logging.getLogger(__name__)

_STREAM_CHUNK = 4096  # bytes per streaming read


class OpenAITTSBackend(TTSBackend):
    """
    OpenAI TTS backend using the official openai Python SDK.

    The openai package is imported lazily inside each method so that the
    module can be imported even when openai is not installed —
    is_available() will return False in that case.
    """

    def __init__(self, config: BackendConfig) -> None:
        self._cfg = config
        self._client = None  # lazy init

    # ------------------------------------------------------------------
    # TTSBackend interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "openai"

    @property
    def supports_cloning(self) -> bool:
        return False

    def is_available(self) -> bool:
        if not self._cfg.openai_api_key:
            _log.debug("OpenAI backend unavailable: OPENAI_API_KEY not set")
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            _log.debug("OpenAI backend unavailable: openai package not installed")
            return False

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        """Return complete audio bytes (MP3)."""
        client = self._get_client()
        voice = voice_id or self._cfg.openai_voice

        _log.info("OpenAI TTS: synthesize %d chars, voice=%s", len(text), voice)
        response = client.audio.speech.create(
            model=self._cfg.openai_model,
            voice=voice,
            input=text,
            response_format="mp3",
        )
        return response.content

    def stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        """Stream MP3 audio chunks as they arrive from the API."""
        client = self._get_client()
        voice = voice_id or self._cfg.openai_voice

        _log.info("OpenAI TTS: stream %d chars, voice=%s", len(text), voice)
        with client.audio.speech.with_streaming_response.create(
            model=self._cfg.openai_model,
            voice=voice,
            input=text,
            response_format="mp3",
        ) as response:
            for chunk in response.iter_bytes(chunk_size=_STREAM_CHUNK):
                if chunk:
                    yield chunk

    def estimate_cost(self, text: str) -> float:
        return len(text) / 1_000_000 * self._cfg.openai_cost_per_1m_chars

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai package is not installed. Run: pip install openai"
                ) from exc
            self._client = OpenAI(api_key=self._cfg.openai_api_key)
        return self._client
