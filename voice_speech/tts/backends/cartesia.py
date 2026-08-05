"""
backends/cartesia.py — Cartesia Sonic backend (latency-critical API path).

Evaluation summary (Task V2)
-----------------------------
Model     : sonic-2 (default)
Quality   : 4.0 / 5
TTFA      : ~65 ms p50  (lowest of all evaluated API options)
Streaming : yes — WebSocket-native
Cost      : ~$43 / 1M chars (mid estimate)
Cloning   : yes — Pro tier (gated by ENABLE_VOICE_CLONING feature flag)
License   : commercial — standard Cartesia API ToS

Routing role
------------
LATENCY-CRITICAL path: selected when RouterContext.latency_critical=True.
Also selected for voice cloning when ENABLE_VOICE_CLONING=true and
ElevenLabs is unavailable.

References
----------
https://docs.cartesia.ai/
https://pypi.org/project/cartesia/
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


class CartesiaBackend(TTSBackend):
    """
    Cartesia Sonic backend using the official cartesia Python SDK.

    The cartesia package is imported lazily so the module loads even when
    the package is absent — is_available() will return False in that case.
    """

    def __init__(self, config: BackendConfig) -> None:
        self._cfg = config
        self._client = None  # lazy init

    # ------------------------------------------------------------------
    # TTSBackend interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "cartesia"

    @property
    def supports_cloning(self) -> bool:
        # Voice cloning requires a Pro-tier API key.
        # The capability is declared here; the feature flag gates its use.
        return True

    def is_available(self) -> bool:
        if not self._cfg.cartesia_api_key:
            _log.debug("Cartesia backend unavailable: CARTESIA_API_KEY not set")
            return False
        try:
            import cartesia  # noqa: F401
            return True
        except ImportError:
            _log.debug("Cartesia backend unavailable: cartesia package not installed")
            return False

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        """Collect the full audio buffer from the streaming WebSocket API."""
        chunks = list(self.stream(text, voice_id=voice_id))
        return b"".join(chunks)

    def stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        """Stream raw PCM audio chunks via Cartesia's WebSocket API."""
        client = self._get_client()
        voice = voice_id or self._cfg.cartesia_voice_id

        _log.info("Cartesia TTS: stream %d chars, voice=%s", len(text), voice)

        output_format = {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 24000,
        }

        for chunk in client.tts.bytes(
            model_id=self._cfg.cartesia_model_id,
            transcript=text,
            voice={"id": voice},
            output_format=output_format,
        ):
            if chunk:
                yield chunk

    def estimate_cost(self, text: str) -> float:
        return len(text) / 1_000_000 * self._cfg.cartesia_cost_per_1m_chars

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            try:
                from cartesia import Cartesia  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "cartesia package is not installed. Run: pip install cartesia"
                ) from exc
            self._client = Cartesia(api_key=self._cfg.cartesia_api_key)
        return self._client
