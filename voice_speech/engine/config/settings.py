from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load .env from voice_speech/ or workspace root
_base_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(_base_dir / ".env")
load_dotenv(_base_dir.parent / ".env")
load_dotenv()


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


@dataclass
class Settings:
    """Top-level unified Riva settings container."""
    vad: VADConfig = field(default_factory=VADConfig)
    gemini: GeminiLiveConfig = field(default_factory=GeminiLiveConfig)
