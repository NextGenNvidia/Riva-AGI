"""TTS backends package."""
from voice_speech.tts.backends.base import TTSBackend
from voice_speech.tts.backends.openai_tts import OpenAITTSBackend
from voice_speech.tts.backends.cartesia import CartesiaBackend
from voice_speech.tts.backends.elevenlabs import ElevenLabsBackend
from voice_speech.tts.backends.azure_tts import AzureTTSBackend
from voice_speech.tts.backends.piper import PiperBackend

__all__ = [
    "TTSBackend",
    "OpenAITTSBackend",
    "CartesiaBackend",
    "ElevenLabsBackend",
    "AzureTTSBackend",
    "PiperBackend",
]
