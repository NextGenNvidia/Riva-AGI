"""Unit tests for Multilingual System Instructions & Persona Prompts."""

from voice_speech.engine.config.prompts import (
    get_system_instruction,
    BASE_INSTRUCTION,
    LANGUAGE_DIRECTIVES,
)


def test_base_instruction():
    assert "Riva" in BASE_INSTRUCTION
    assert "CORE RULES" in BASE_INSTRUCTION


def test_language_directives():
    for lang in ["auto", "hindi", "english", "hinglish"]:
        instruction = get_system_instruction(lang)
        assert BASE_INSTRUCTION in instruction
        assert LANGUAGE_DIRECTIVES[lang] in instruction


def test_unknown_language_fallback():
    instruction = get_system_instruction("klingon")
    assert LANGUAGE_DIRECTIVES["auto"] in instruction
