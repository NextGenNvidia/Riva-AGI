"""Backend Configuration Module for Riva-AGI.

Loads environment variables, manages configuration settings for API,
voice gateway, orchestration, and frontend integration.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Resolve repository root
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

# Load environment files: project root .env and voice_speech/.env
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "voice_speech" / ".env")


class BackendConfig:
    """Central configuration class for Riva-AGI Backend."""

    def __init__(self):
        # Server settings
        self.host: str = os.getenv("API_HOST", os.getenv("HOST", "0.0.0.0"))
        self.port: int = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

        # Paths
        self.repo_root: Path = REPO_ROOT
        self.backend_dir: Path = BACKEND_DIR
        self.voice_speech_dir: Path = REPO_ROOT / "voice_speech"
        self.web_dir: Path = self.voice_speech_dir / "web"

        # CORS Origins
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").strip()
        raw_origins = [
            frontend_url,
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:8000",
        ]
        # Keep unique and non-empty
        self.allowed_origins: List[str] = list(dict.fromkeys([o for o in raw_origins if o]))

        # WebSocket Allowed Origins
        self.allowed_ws_origins: set = {
            "http://localhost:8000",
            "http://localhost",
            "http://127.0.0.1:8000",
            "https://localhost:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        }


config = BackendConfig()
