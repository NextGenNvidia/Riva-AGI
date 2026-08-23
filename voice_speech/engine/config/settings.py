"""
Configuration and settings for Riva Ultra-Low-Latency Voice Assistant.
"""

from dataclasses import dataclass, field
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AudioInputConfig:
    """Microphone capture configuration."""
    sample_rate: int = 16000  # Gemini Live native input rate (Hz)
    channels: int = 1         # Mono
    dtype: str = "int16"      # 16-bit signed little-endian PCM
    frame_duration_ms: int = 20  # 20ms frame duration
    device_index: Optional[int] = None  # None for system default
    output_mode: str = os.getenv("AUDIO_OUTPUT_MODE", "auto")  # "auto", "earphones", "speaker"

    @property
    def samples_per_frame(self) -> int:
        return int(self.sample_rate * (self.frame_duration_ms / 1000.0))  # 320 samples for 20ms @ 16kHz

    @property
    def bytes_per_frame(self) -> int:
        return self.samples_per_frame * 2  # 640 bytes for 16-bit PCM

    @property
    def mime_type(self) -> str:
        return f"audio/pcm;rate={self.sample_rate}"


@dataclass
class AudioOutputConfig:
    """Audio output and playback configuration."""
    sample_rate: int = 24000  # Gemini Live native output rate (Hz)
    channels: int = 1         # Mono
    dtype: str = "int16"      # 16-bit signed little-endian PCM
    device_index: Optional[int] = None  # None for system default
    prebuffer_bytes: int = 1920  # ~40ms buffer (2 chunks of 20ms @ 24kHz)
    blocksize: int = 480         # 20ms callback block size @ 24kHz
    max_queue_size: int = 50     # Queue limit to prevent backlog accumulation


@dataclass
class VADConfig:
    """Server-side Voice Activity Detection configuration on Google's servers."""
    disabled: bool = False
    prefix_padding_ms: int = int(os.getenv("VAD_PREFIX_PADDING_MS", "50"))       # Fast 50ms look-back
    silence_duration_ms: int = int(os.getenv("VAD_SILENCE_DURATION_MS", "120"))  # Fast 120ms turn completion
    start_sensitivity: str = os.getenv("VAD_START_SENSITIVITY", "START_SENSITIVITY_HIGH")  # Catches speech onset instantly
    end_sensitivity: str = os.getenv("VAD_END_SENSITIVITY", "END_SENSITIVITY_HIGH")        # Immediate turnaround upon question end


@dataclass
class GeminiLiveConfig:
    """Gemini Live API Configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview"))
    voice_name: str = os.getenv("GEMINI_VOICE", "Aoede")  # Options: Aoede, Charon, Fenrir, Kore, Puck
    thinking_level: str = os.getenv("THINKING_LEVEL", "MINIMAL")  # MINIMAL or LOW
    response_modalities: List[str] = field(default_factory=lambda: ["AUDIO"])
    system_instruction: str = (
        "You are Riva, built by NextGen SuperComputing Club at KIET Deemed to be University Ghaziabad Delhi NCR. "
        "You are a real-time conversational voice assistant speaking directly to the user in fluent, natural Hindi.\n\n"
        "CORE RULES:\n"
        "1. Accurately understand and answer the user's question directly in Hindi.\n"
        "2. Keep your answers concise, clear, and relevant.\n"
        "3. Never narrate actions (no 'Thinking', 'Processing'). Speak your answer directly."
    )


@dataclass
class Settings:
    """Top-level unified Riva settings container."""
    audio_in: AudioInputConfig = field(default_factory=AudioInputConfig)
    audio_out: AudioOutputConfig = field(default_factory=AudioOutputConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    gemini: GeminiLiveConfig = field(default_factory=GeminiLiveConfig)
