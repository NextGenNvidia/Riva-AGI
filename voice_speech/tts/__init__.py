"""TTS package."""
try:
    from voice_speech.tts.router import TTSRouter, RouterContext
    from voice_speech.tts.player import play_audio, save_audio
    from voice_speech.tts.config import RouterConfig, BackendConfig
    from voice_speech.tts.logger import TTSLogger
except ImportError:
    from router import TTSRouter, RouterContext
    from player import play_audio, save_audio
    from config import RouterConfig, BackendConfig
    from logger import TTSLogger

__all__ = [
    "TTSRouter",
    "RouterContext",
    "play_audio",
    "save_audio",
    "RouterConfig",
    "BackendConfig",
    "TTSLogger",
]
