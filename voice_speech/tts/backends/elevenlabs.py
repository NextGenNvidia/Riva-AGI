"""
backends/elevenlabs.py — ElevenLabs backend (premium voice / cloning).

Evaluation summary (Task V2)
-----------------------------
Model     : eleven_turbo_v2_5  (Flash/Turbo — lowest latency in EL lineup)
Quality   : 4.7 / 5  (best voice quality of all evaluated options)
TTFA      : ~75 ms p50
Streaming : yes — SSE + WebSocket
Cost      : ~$75 / 1M chars (Turbo estimate; ~3–6x more than OpenAI)
Cloning   : yes — voice cloning from a 5-second audio sample
License   : commercial — standard ElevenLabs API ToS

Routing role
------------
PREMIUM path: selected when RouterContext.premium=True.
CLONING path: selected when RouterContext.need_cloning=True and
              ENABLE_VOICE_CLONING=true (FR-15/17).
Falls back to OpenAI / Piper if ELEVENLABS_API_KEY is not set.

This backend is NEVER selected by default routing — only when explicitly
requested via premium=True or need_cloning=True, to control cost.

References
----------
https://elevenlabs.io/docs/api-reference/text-to-speech
https://pypi.org/project/elevenlabs/
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


class ElevenLabsBackend(TTSBackend):
    """
    ElevenLabs TTS backend using the official elevenlabs Python SDK.

    The elevenlabs package is imported lazily so the module loads even
    when the package is absent — is_available() returns False in that case.
    """

    def __init__(self, config: BackendConfig) -> None:
        self._cfg = config
        self._client = None  # lazy init

    # ------------------------------------------------------------------
    # TTSBackend interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def supports_cloning(self) -> bool:
        return True

    def is_available(self) -> bool:
        if not self._cfg.elevenlabs_api_key:
            _log.debug("ElevenLabs backend unavailable: ELEVENLABS_API_KEY not set")
            return False
        try:
            import elevenlabs  # noqa: F401
            return True
        except ImportError:
            _log.debug(
                "ElevenLabs backend unavailable: elevenlabs package not installed"
            )
            return False

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        """Return complete MP3 audio bytes."""
        chunks = list(self.stream(text, voice_id=voice_id))
        return b"".join(chunks)

    def stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        """Yield MP3 audio chunks via ElevenLabs streaming API."""
        client = self._get_client()
        voice = voice_id or self._cfg.elevenlabs_voice_id

        _log.info("ElevenLabs TTS: stream %d chars, voice=%s", len(text), voice)

        audio_stream = client.text_to_speech.stream(
            text=text,
            voice_id=voice,
            model_id=self._cfg.elevenlabs_model_id,
            output_format="mp3_44100_128",
        )
        for chunk in audio_stream:
            if isinstance(chunk, bytes) and chunk:
                yield chunk

    def estimate_cost(self, text: str) -> float:
        return len(text) / 1_000_000 * self._cfg.elevenlabs_cost_per_1m_chars

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            try:
                from elevenlabs.client import ElevenLabs  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "elevenlabs package is not installed. "
                    "Run: pip install elevenlabs"
                ) from exc
            self._client = ElevenLabs(api_key=self._cfg.elevenlabs_api_key)
        return self._client
