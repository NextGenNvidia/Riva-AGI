"""
config.py — Configuration dataclasses and environment-variable loading.

All API keys and tunable parameters live here. The rest of the module
imports from this file rather than reading os.environ directly, so
configuration is easy to override in tests.

Usage
-----
    # Default config (reads from environment):
    cfg = RouterConfig()

    # Override in tests:
    cfg = RouterConfig(
        backend=BackendConfig(openai_api_key="test-key"),
        cost_budget_per_request_usd=0.01,
    )
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

def _load_env_file() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(override=False)
    except ImportError:
        pass

    # Search upwards from current directory and file location for .env file
    starts = [Path.cwd(), Path(__file__).resolve().parent]
    for start in starts:
        curr = start
        while curr != curr.parent:
            env_path = curr / ".env"
            if env_path.exists():
                try:
                    with open(env_path, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k, v = k.strip(), v.strip().strip("'\"")
                                # Overwrite if not set or if set to empty string
                                if v and (k not in os.environ or not os.environ[k].strip()):
                                    os.environ[k] = v
                    return
                except Exception:
                    pass
            curr = curr.parent

_load_env_file()


# ---------------------------------------------------------------------------
# Backend-level config
# ---------------------------------------------------------------------------

@dataclass
class BackendConfig:
    """Per-backend settings loaded from environment variables."""

    # --- OpenAI TTS ---
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.environ.get("OPENAI_TTS_MODEL", "tts-1")
    )
    openai_voice: str = field(
        default_factory=lambda: os.environ.get("OPENAI_TTS_VOICE", "alloy")
    )
    # Cost per 1M characters in USD — tts-1=$15, tts-1-hd=$30
    openai_cost_per_1m_chars: float = 15.0

    # --- Cartesia ---
    cartesia_api_key: str = field(
        default_factory=lambda: os.environ.get("CARTESIA_API_KEY", "")
    )
    cartesia_model_id: str = field(
        default_factory=lambda: os.environ.get("CARTESIA_MODEL_ID", "sonic-2")
    )
    cartesia_voice_id: str = field(
        default_factory=lambda: os.environ.get(
            "CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091"
        )
    )
    # Cost per 1M characters in USD (mid estimate ~$43)
    cartesia_cost_per_1m_chars: float = 43.0

    # --- ElevenLabs ---
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", "")
    )
    elevenlabs_model_id: str = field(
        default_factory=lambda: os.environ.get(
            "ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5"
        )
    )
    elevenlabs_voice_id: str = field(
        default_factory=lambda: os.environ.get(
            "ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"  # George (premade voice compatible with free tier)
        )
    )
    # Cost per 1M characters in USD (Turbo estimate ~$75)
    elevenlabs_cost_per_1m_chars: float = 75.0

    # --- Azure Neural TTS ---
    azure_speech_key: str = field(
        default_factory=lambda: os.environ.get("AZURE_SPEECH_KEY", "")
    )
    azure_speech_region: str = field(
        default_factory=lambda: os.environ.get("AZURE_SPEECH_REGION", "eastus")
    )
    azure_speech_voice: str = field(
        default_factory=lambda: os.environ.get(
            "AZURE_SPEECH_VOICE", "en-US-AriaNeural"
        )
    )
    # Output format: Audio16Khz128KBitRateMonoMp3
    # Cost per 1M characters in USD (~$16 Neural TTS standard)
    azure_cost_per_1m_chars: float = 16.0

    # --- Piper (local) ---
    piper_binary: str = field(
        default_factory=lambda: os.environ.get("PIPER_BINARY", "piper")
    )
    piper_model: str = field(
        default_factory=lambda: os.environ.get(
            "PIPER_MODEL", "en_US-lessac-medium.onnx"
        )
    )
    piper_model_config: str = field(
        default_factory=lambda: os.environ.get(
            "PIPER_MODEL_CONFIG", ""
        )
    )


# ---------------------------------------------------------------------------
# Router-level config
# ---------------------------------------------------------------------------

@dataclass
class RouterConfig:
    """
    Router behaviour and budget settings.

    Feature flags
    -------------
    enable_voice_cloning : bool
        When False (default), the router never selects a cloning-capable
        backend for FR-15/17. Set ENABLE_VOICE_CLONING=true to enable.
    """

    # Cost budget per request — router will log a WARNING if exceeded
    cost_budget_per_request_usd: float = field(
        default_factory=lambda: float(
            os.environ.get("TTS_COST_BUDGET_PER_REQUEST", "0.005")
        )
    )

    # Latency targets (ms) — used for logging and routing decisions
    latency_target_api_ms: float = 300.0    # NFR-2: < 300 ms TTFA via API
    latency_target_local_ms: float = 150.0  # NFR-4: < 150 ms TTFA locally

    # Feature flags
    enable_voice_cloning: bool = field(
        default_factory=lambda: os.environ.get(
            "ENABLE_VOICE_CLONING", "false"
        ).lower() == "true"
    )

    # Log file path
    log_file: str = field(
        default_factory=lambda: os.environ.get(
            "TTS_LOG_FILE", "tts_requests.jsonl"
        )
    )

    # Backend config (composed in)
    backend: BackendConfig = field(default_factory=BackendConfig)
