"""
tests/test_unit.py — Unit tests for the TTS module (no network required).

Run with:
    cd /home/alex/Desktop/TTSv2
    python -m pytest tests/test_unit.py -v

All tests use mocked backends — no live API calls are made.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest
import sys

# Allow running directly from root or voice_speech folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

try:
    from voice_speech.tts.backends.base import TTSBackend
    from voice_speech.tts.config import RouterConfig, BackendConfig
    from voice_speech.tts.logger import TTSLogger, RequestRecord
    from voice_speech.tts.router import TTSRouter, RouterContext
except ImportError:
    from backends.base import TTSBackend
    from config import RouterConfig, BackendConfig
    from logger import TTSLogger, RequestRecord
    from router import TTSRouter, RouterContext


# ---------------------------------------------------------------------------
# Helpers: minimal fake backends
# ---------------------------------------------------------------------------

class _FakeBackend(TTSBackend):
    def __init__(self, name: str, available: bool = True, cloning: bool = False):
        self._name = name
        self._available = available
        self._cloning = cloning
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def supports_cloning(self) -> bool:
        return self._cloning

    def is_available(self) -> bool:
        return self._available

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        self.calls.append(text)
        return b"FAKE_AUDIO"

    def stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        self.calls.append(text)
        yield b"FAKE_AUDIO"

    def estimate_cost(self, text: str) -> float:
        return 0.001 * len(text)


def _temp_log_file() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()
    return tmp.name


def _make_router(**backend_overrides) -> TTSRouter:
    """Build a TTSRouter whose backends can be overridden with fakes."""
    config = RouterConfig(
        log_file=_temp_log_file(),
        backend=BackendConfig(
            openai_api_key="test-key",
            cartesia_api_key="test-key",
            elevenlabs_api_key="test-key",
            azure_speech_key="test-key",
            azure_speech_region="eastus",
            piper_binary="piper",
            piper_model="/fake/model.onnx",
        ),
    )
    router = TTSRouter(config=config)
    defaults = {
        "openai":     _FakeBackend("openai"),
        "cartesia":   _FakeBackend("cartesia"),
        "elevenlabs": _FakeBackend("elevenlabs", cloning=True),
        "azure":      _FakeBackend("azure"),
        "piper":      _FakeBackend("piper"),
    }
    defaults.update(backend_overrides)
    router._backends = defaults
    return router


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------

class TestRouting:

    def test_default_path_picks_elevenlabs(self):
        router = _make_router()
        audio = router.synthesize("hello", RouterContext())
        assert audio == b"FAKE_AUDIO"
        assert router._backends["elevenlabs"].calls == ["hello"]

    def test_default_path_falls_back_to_openai_when_elevenlabs_unavailable(self):
        router = _make_router(elevenlabs=_FakeBackend("elevenlabs", available=False))
        audio = router.synthesize("hello", RouterContext())
        assert router._backends["openai"].calls == ["hello"]

    def test_default_path_falls_back_to_azure_when_elevenlabs_and_openai_unavailable(self):
        router = _make_router(
            elevenlabs=_FakeBackend("elevenlabs", available=False),
            openai=_FakeBackend("openai", available=False),
        )
        audio = router.synthesize("hello", RouterContext())
        assert router._backends["azure"].calls == ["hello"]

    def test_default_path_falls_back_to_piper_when_api_unavailable(self):
        router = _make_router(
            elevenlabs=_FakeBackend("elevenlabs", available=False),
            openai=_FakeBackend("openai", available=False),
            azure=_FakeBackend("azure", available=False),
        )
        audio = router.synthesize("hello", RouterContext())
        assert router._backends["piper"].calls == ["hello"]

    def test_offline_always_uses_piper(self):
        router = _make_router()
        router.synthesize("hello", RouterContext(network_available=False))
        assert router._backends["piper"].calls == ["hello"]
        assert router._backends["openai"].calls == []

    def test_latency_critical_picks_cartesia(self):
        router = _make_router()
        router.synthesize("hello", RouterContext(latency_critical=True))
        assert router._backends["cartesia"].calls == ["hello"]

    def test_latency_critical_falls_back_to_openai(self):
        router = _make_router(cartesia=_FakeBackend("cartesia", available=False))
        router.synthesize("hello", RouterContext(latency_critical=True))
        assert router._backends["openai"].calls == ["hello"]

    def test_premium_picks_elevenlabs(self):
        router = _make_router()
        router.synthesize("hello", RouterContext(premium=True))
        assert router._backends["elevenlabs"].calls == ["hello"]

    def test_premium_falls_back_to_openai(self):
        router = _make_router(elevenlabs=_FakeBackend("elevenlabs", available=False))
        router.synthesize("hello", RouterContext(premium=True))
        assert router._backends["openai"].calls == ["hello"]

    def test_force_backend_openai(self):
        router = _make_router()
        router.synthesize("hello", RouterContext(force_backend="openai"))
        assert router._backends["openai"].calls == ["hello"]

    def test_force_backend_piper(self):
        router = _make_router()
        router.synthesize("hello", RouterContext(force_backend="piper"))
        assert router._backends["piper"].calls == ["hello"]

    def test_force_backend_azure(self):
        router = _make_router()
        router.synthesize("hello", RouterContext(force_backend="azure"))
        assert router._backends["azure"].calls == ["hello"]

    def test_force_backend_unknown_raises_value_error(self):
        router = _make_router()
        with pytest.raises(ValueError, match="Unknown backend"):
            router.synthesize("hello", RouterContext(force_backend="bogus"))

    def test_force_backend_unavailable_raises_runtime_error(self):
        router = _make_router(openai=_FakeBackend("openai", available=False))
        with pytest.raises(RuntimeError, match="not available"):
            router.synthesize("hello", RouterContext(force_backend="openai"))

    def test_no_backends_available_raises(self):
        router = _make_router(
            openai=_FakeBackend("openai", available=False),
            cartesia=_FakeBackend("cartesia", available=False),
            elevenlabs=_FakeBackend("elevenlabs", available=False),
            azure=_FakeBackend("azure", available=False),
            piper=_FakeBackend("piper", available=False),
        )
        with pytest.raises(RuntimeError, match="No backend available"):
            router.synthesize("hello", RouterContext())


# ---------------------------------------------------------------------------
# Cloning tests
# ---------------------------------------------------------------------------

class TestCloning:

    def test_cloning_flag_off_falls_back_with_warning(self, caplog):
        config = RouterConfig(
            enable_voice_cloning=False,
            log_file=_temp_log_file(),
            backend=BackendConfig(),
        )
        router = _make_router()
        router._config = config
        with caplog.at_level(logging.WARNING):
            router.synthesize("hello", RouterContext(need_cloning=True))
        assert any("ENABLE_VOICE_CLONING" in r.message for r in caplog.records)

    def test_cloning_flag_on_picks_elevenlabs(self):
        config = RouterConfig(
            enable_voice_cloning=True,
            log_file=_temp_log_file(),
            backend=BackendConfig(),
        )
        router = _make_router()
        router._config = config
        router.synthesize("hello", RouterContext(need_cloning=True))
        assert router._backends["elevenlabs"].calls == ["hello"]

    def test_cloning_no_capable_backend_raises(self):
        config = RouterConfig(
            enable_voice_cloning=True,
            log_file=_temp_log_file(),
            backend=BackendConfig(),
        )
        router = _make_router(
            elevenlabs=_FakeBackend("elevenlabs", available=False, cloning=True),
            cartesia=_FakeBackend("cartesia", available=False, cloning=True),
        )
        router._config = config
        with pytest.raises(RuntimeError, match="no cloning-capable backend"):
            router.synthesize("hello", RouterContext(need_cloning=True))


# ---------------------------------------------------------------------------
# Logger tests
# ---------------------------------------------------------------------------

class TestLogger:

    def test_record_writes_valid_json(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        config = RouterConfig(log_file=log_path, backend=BackendConfig())
        logger = TTSLogger(config)

        with logger.record("openai", "hello world", cost_usd=0.001) as rec:
            rec.mark_first_audio()

        with open(log_path) as fh:
            line = fh.readline()
        record = json.loads(line)

        assert record["backend"] == "openai"
        assert record["char_count"] == 11
        assert record["cost_usd"] == 0.001
        assert record["success"] is True
        assert record["error"] is None
        assert record["ttfa_ms"] is not None
        assert record["total_ms"] >= 0

    def test_record_captures_exception(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        config = RouterConfig(log_file=log_path, backend=BackendConfig())
        logger = TTSLogger(config)

        with pytest.raises(ValueError):
            with logger.record("piper", "boom", cost_usd=0.0) as rec:
                raise ValueError("synthesis exploded")

        with open(log_path) as fh:
            record = json.loads(fh.readline())
        assert record["success"] is False
        assert "synthesis exploded" in record["error"]

    def test_get_summary_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        config = RouterConfig(log_file=log_path, backend=BackendConfig())
        logger = TTSLogger(config)
        result = logger.get_summary()
        assert result["total_requests"] == 0

    def test_get_summary_aggregates(self):
        with tempfile.NamedTemporaryFile(mode="w",
                                          delete=False, suffix=".jsonl") as f:
            log_path = f.name

        config = RouterConfig(log_file=log_path, backend=BackendConfig())
        logger = TTSLogger(config)

        for backend in ["openai", "openai", "piper"]:
            with logger.record(backend, "test", cost_usd=0.001) as rec:
                rec.mark_first_audio()

        summary = logger.get_summary()
        assert summary["total_requests"] == 3
        assert summary["backends_used"]["openai"] == 2
        assert summary["backends_used"]["piper"] == 1
        assert summary["total_cost_usd"] == pytest.approx(0.003)

    def test_cost_warning_emitted(self, caplog):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        config = RouterConfig(
            log_file=log_path,
            cost_budget_per_request_usd=0.0001,
            backend=BackendConfig(),
        )
        logger = TTSLogger(config)

        with caplog.at_level(logging.WARNING):
            with logger.record("elevenlabs", "x", cost_usd=1.0) as rec:
                pass

        assert any("exceeded" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Backend availability tests
# ---------------------------------------------------------------------------

class TestAvailability:

    def test_openai_unavailable_without_key(self):
        try:
            from voice_speech.tts.backends.openai_tts import OpenAITTSBackend
        except ImportError:
            from backends.openai_tts import OpenAITTSBackend
        bc = BackendConfig(openai_api_key="")
        backend = OpenAITTSBackend(bc)
        assert backend.is_available() is False

    def test_cartesia_unavailable_without_key(self):
        try:
            from voice_speech.tts.backends.cartesia import CartesiaBackend
        except ImportError:
            from backends.cartesia import CartesiaBackend
        bc = BackendConfig(cartesia_api_key="")
        backend = CartesiaBackend(bc)
        assert backend.is_available() is False

    def test_elevenlabs_unavailable_without_key(self):
        try:
            from voice_speech.tts.backends.elevenlabs import ElevenLabsBackend
        except ImportError:
            from backends.elevenlabs import ElevenLabsBackend
        bc = BackendConfig(elevenlabs_api_key="")
        backend = ElevenLabsBackend(bc)
        assert backend.is_available() is False

    def test_azure_unavailable_without_key(self):
        try:
            from voice_speech.tts.backends.azure_tts import AzureTTSBackend
        except ImportError:
            from backends.azure_tts import AzureTTSBackend
        bc = BackendConfig(azure_speech_key="")
        backend = AzureTTSBackend(bc)
        assert backend.is_available() is False

    def test_piper_unavailable_without_binary(self):
        try:
            from voice_speech.tts.backends.piper import PiperBackend
        except ImportError:
            from backends.piper import PiperBackend
        bc = BackendConfig(piper_binary="/nonexistent/piper", piper_model="")
        backend = PiperBackend(bc)
        assert backend.is_available() is False

    def test_router_status_returns_dict(self):
        router = _make_router()
        status = router.status()
        assert set(status.keys()) == {"openai", "cartesia", "elevenlabs", "azure", "piper"}
        for v in status.values():
            assert isinstance(v, bool)
