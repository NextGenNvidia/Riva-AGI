"""Unit tests for Gemini Live Session & Connection Config Builder."""

import pytest
from voice_speech.engine.config.settings import Settings
from voice_speech.engine.gemini.session import (
    build_connect_config,
    build_vad_config,
    build_speech_config,
    build_thinking_config,
    VALID_VOICES,
)


def test_build_connect_config_shape():
    settings = Settings()
    config = build_connect_config(
        settings=settings,
        voice="Kore",
        language="hindi",
        resumption_handle="test_handle_123",
    )

    assert config.response_modalities == ["AUDIO"]
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Kore"
    assert config.session_resumption.handle == "test_handle_123"
    assert config.context_window_compression.trigger_tokens == 16000
    assert config.context_window_compression.sliding_window.target_tokens == 8000
    assert len(config.tools) > 0


def test_build_connect_config_invalid_voice_fallback():
    settings = Settings()
    config = build_connect_config(
        settings=settings,
        voice="NonExistentVoice",
        language="english",
    )
    # Should fallback to default settings voice
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name in VALID_VOICES


def test_build_vad_config():
    settings = Settings()
    vad = build_vad_config(settings.vad)
    assert vad.disabled == settings.vad.disabled
    assert vad.prefix_padding_ms == settings.vad.prefix_padding_ms
    assert vad.silence_duration_ms == settings.vad.silence_duration_ms


def test_build_thinking_config():
    assert build_thinking_config("MINIMAL") is None
    assert build_thinking_config("LOW") is None
    assert build_thinking_config("HIGH") is not None
