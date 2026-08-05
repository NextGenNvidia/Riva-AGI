"""TTS backends package."""
try:
    from voice_speech.tts.backends.base import TTSBackend
    from voice_speech.tts.backends.openai_tts import OpenAITTSBackend
    from voice_speech.tts.backends.cartesia import CartesiaBackend
    from voice_speech.tts.backends.elevenlabs import ElevenLabsBackend
    from voice_speech.tts.backends.azure_tts import AzureTTSBackend
    from voice_speech.tts.backends.piper import PiperBackend
except ImportError:
    from .base import TTSBackend
    from .openai_tts import OpenAITTSBackend
    from .cartesia import CartesiaBackend
    from .elevenlabs import ElevenLabsBackend
    from .azure_tts import AzureTTSBackend
    from .piper import PiperBackend

__all__ = [
    "TTSBackend",
    "OpenAITTSBackend",
    "CartesiaBackend",
    "ElevenLabsBackend",
    "AzureTTSBackend",
    "PiperBackend",
]
