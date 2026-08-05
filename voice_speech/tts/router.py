"""
router.py — Context-aware backend selection for the TTS module.

The TTSRouter is the primary entry point for the rest of the pipeline.
It selects the appropriate backend based on the RouterContext, synthesizes
audio, and records per-request metrics via TTSLogger.

Routing priority (first match wins)
-------------------------------------
1. force_backend     — manual override (FR-6)
2. need_cloning      — select a cloning-capable backend (FR-17, feature-flagged)
3. network_available == False  → Piper (FR-8)
4. premium == True   → ElevenLabs → OpenAI → Piper (FR-9)
5. latency_critical == True    → Cartesia → OpenAI → Piper (FR-10)
6. default           → OpenAI → Piper

If the selected backend is unavailable, the router falls back down the
priority chain rather than raising immediately (FR-7).

Usage
-----
    from tts_module import TTSRouter, RouterContext

    router = TTSRouter()

    # Simple synthesis
    audio = router.synthesize("Hello!", RouterContext())

    # Streaming synthesis
    for chunk in router.stream("Hello!", RouterContext(latency_critical=True)):
        player.play_audio(chunk)

    # Session summary
    print(router.logger.get_summary())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterator

try:
    from voice_speech.tts.backends.base import TTSBackend
    from voice_speech.tts.config import RouterConfig
    from voice_speech.tts.logger import TTSLogger
    from voice_speech.tts.backends.openai_tts import OpenAITTSBackend
    from voice_speech.tts.backends.cartesia import CartesiaBackend
    from voice_speech.tts.backends.elevenlabs import ElevenLabsBackend
    from voice_speech.tts.backends.azure_tts import AzureTTSBackend
    from voice_speech.tts.backends.piper import PiperBackend
except ImportError:
    from backends.base import TTSBackend
    from config import RouterConfig
    from logger import TTSLogger
    from backends.openai_tts import OpenAITTSBackend
    from backends.cartesia import CartesiaBackend
    from backends.elevenlabs import ElevenLabsBackend
    from backends.azure_tts import AzureTTSBackend
    from backends.piper import PiperBackend

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RouterContext — caller-supplied per-request context
# ---------------------------------------------------------------------------

@dataclass
class RouterContext:
    """
    Per-request context that the router uses to select a backend.

    Parameters
    ----------
    network_available : bool
        Set False to force the local (Piper) path — useful for offline mode
        or when the orchestrator detects network loss (FR-8).
    latency_critical : bool
        Hints that this turn needs the lowest possible TTFA; the router
        prefers Cartesia over OpenAI (FR-10).
    premium : bool
        Route to ElevenLabs for maximum voice quality (opt-in, costs ~3–6x
        more than the default) (FR-9).
    force_backend : str | None
        Override all heuristics and use a specific backend by name.
        Valid names: "openai", "cartesia", "elevenlabs", "azure", "piper".
        Raises ValueError if the name is unknown; RuntimeError if unavailable
        (FR-6).
    voice_id : str | None
        Backend-specific voice identifier. Passed through to the selected
        backend's synthesize/stream call (FR-4).
    need_cloning : bool
        If True, the router selects a backend that supports voice cloning,
        subject to the ENABLE_VOICE_CLONING feature flag (FR-15/17).
    """

    network_available: bool = True
    latency_critical: bool = False
    premium: bool = False
    force_backend: str | None = None
    voice_id: str | None = None
    need_cloning: bool = False


# ---------------------------------------------------------------------------
# TTSRouter
# ---------------------------------------------------------------------------

class TTSRouter:
    """
    Context-aware TTS router.

    Parameters
    ----------
    config : RouterConfig | None
        If None, a default RouterConfig (reading from env vars) is used.
    """

    def __init__(self, config: RouterConfig | None = None) -> None:
        self._config = config or RouterConfig()
        self._logger = TTSLogger(self._config)

        bc = self._config.backend
        self._backends: dict[str, TTSBackend] = {
            "openai":     OpenAITTSBackend(bc),
            "cartesia":   CartesiaBackend(bc),
            "elevenlabs": ElevenLabsBackend(bc),
            "azure":      AzureTTSBackend(bc),
            "piper":      PiperBackend(bc),
        }

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def logger(self) -> TTSLogger:
        """Access the TTSLogger for session summaries."""
        return self._logger

    # ------------------------------------------------------------------
    # Public synthesis API
    # ------------------------------------------------------------------

    def synthesize(self, text: str, ctx: RouterContext | None = None) -> bytes:
        """
        Synthesize *text* and return the complete audio as bytes.

        Parameters
        ----------
        text : str
            Text to synthesize.
        ctx : RouterContext | None
            Routing context. Uses default context if None.

        Returns
        -------
        bytes
            Raw audio (MP3 or WAV depending on backend).
        """
        ctx = ctx or RouterContext()
        backend = self._select(ctx)
        cost = backend.estimate_cost(text)

        with self._logger.record(backend.name, text, cost_usd=cost) as rec:
            audio = backend.synthesize(text, voice_id=ctx.voice_id)
            rec.mark_first_audio()  # full audio ready = first audio for non-streaming
        return audio

    def stream(
        self, text: str, ctx: RouterContext | None = None
    ) -> Iterator[bytes]:
        """
        Synthesize *text* and yield audio chunks as they arrive.

        The first non-empty chunk signals TTFA. The logger records TTFA
        automatically as the generator is consumed.

        Parameters
        ----------
        text : str
            Text to synthesize.
        ctx : RouterContext | None
            Routing context.

        Yields
        ------
        bytes
            Raw audio chunks (MP3 or WAV).
        """
        ctx = ctx or RouterContext()
        backend = self._select(ctx)
        cost = backend.estimate_cost(text)

        with self._logger.record(backend.name, text, cost_usd=cost) as rec:
            first = True
            for chunk in backend.stream(text, voice_id=ctx.voice_id):
                if first and chunk:
                    rec.mark_first_audio()
                    first = False
                yield chunk

    # ------------------------------------------------------------------
    # Backend selection logic
    # ------------------------------------------------------------------

    def _select(self, ctx: RouterContext) -> TTSBackend:
        """Apply routing priority rules and return an available backend."""

        # 1. Manual override (FR-6)
        if ctx.force_backend:
            return self._force(ctx.force_backend)

        # 2. Cloning required — needs a cloning-capable backend (FR-17)
        if ctx.need_cloning:
            return self._select_cloning(ctx)

        # 3. No network — must use local backend (FR-8)
        if not ctx.network_available:
            return self._require("piper", reason="network_available=False")

        # 4. Premium quality requested (FR-9)
        if ctx.premium:
            return self._pick_first(
                ["elevenlabs", "openai", "azure", "piper"],
                reason="premium=True",
            )

        # 5. Latency-critical path (FR-10)
        if ctx.latency_critical:
            return self._pick_first(
                ["cartesia", "openai", "azure", "piper"],
                reason="latency_critical=True",
            )

        # 6. Default API path (ElevenLabs -> OpenAI -> Azure -> Piper)
        return self._pick_first(
            ["elevenlabs", "openai", "azure", "piper"],
            reason="default",
        )

    def _select_cloning(self, ctx: RouterContext) -> TTSBackend:
        """Handle cloning requests — gated by ENABLE_VOICE_CLONING flag."""
        if not self._config.enable_voice_cloning:
            _log.warning(
                "Router: need_cloning=True but ENABLE_VOICE_CLONING is False. "
                "Falling back to default path. "
                "Set ENABLE_VOICE_CLONING=true to enable voice cloning."
            )
            return self._pick_first(["openai", "piper"], reason="cloning disabled")

        for name in ["elevenlabs", "cartesia"]:
            b = self._backends[name]
            if b.supports_cloning and b.is_available():
                _log.info("Router: selected %s for voice cloning", name)
                return b

        raise RuntimeError(
            "Voice cloning requested but no cloning-capable backend is available. "
            "Configure ELEVENLABS_API_KEY or CARTESIA_API_KEY."
        )

    def _force(self, name: str) -> TTSBackend:
        """Return the explicitly requested backend; raise if unavailable."""
        if name not in self._backends:
            raise ValueError(
                f"Unknown backend {name!r}. "
                f"Valid names: {list(self._backends)}"
            )
        backend = self._backends[name]
        if not backend.is_available():
            raise RuntimeError(
                f"Forced backend {name!r} is not available. "
                "Check API keys and installed packages."
            )
        _log.info("Router: force_backend=%r selected", name)
        return backend

    def _require(self, name: str, reason: str) -> TTSBackend:
        """Return backend *name*; raise clearly if unavailable."""
        backend = self._backends[name]
        if not backend.is_available():
            raise RuntimeError(
                f"Backend {name!r} is required ({reason}) but is not available. "
                "Check PIPER_BINARY and PIPER_MODEL environment variables."
            )
        _log.info("Router: selected %s (%s)", name, reason)
        return backend

    def _pick_first(self, order: list[str], reason: str) -> TTSBackend:
        """
        Try backends in *order* and return the first available one.
        Raises RuntimeError if none are available.
        """
        for name in order:
            b = self._backends[name]
            if b.is_available():
                _log.info("Router: selected %s (%s)", name, reason)
                return b
            _log.debug("Router: %s unavailable, trying next", name)

        raise RuntimeError(
            f"No backend available from candidates {order} (reason: {reason}). "
            "Configure at least one API key or install Piper."
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def status(self) -> dict[str, bool]:
        """Return availability status for all registered backends."""
        return {name: b.is_available() for name, b in self._backends.items()}
