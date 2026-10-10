"""Riva WebSocket Voice Gateway Server Compatibility Layer.

NOTE: The central API and routers have been promoted to the dedicated `Backend` module:
    - Routers: Backend/routers/
    - Services: Backend/services/
    - Main Application: Backend/main.py

This module preserves backwards compatibility for existing launch scripts
(run.sh, run.ps1, run.bat) by delegating to `Backend.main.app`.
"""

import os
import sys
from pathlib import Path

# Ensure parent directory is in sys.path for voice_speech package imports
_pkg_root = str(Path(__file__).resolve().parent.parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from Backend.main import app
from Backend.routers.voice import audio_websocket_endpoint
from Backend.services.voice_service import voice_service

# Re-export key references for backwards compatibility
gemini_client = voice_service.gemini_client
session_manager = voice_service.session_manager
settings = voice_service.settings

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("Backend.main:app", host="0.0.0.0", port=port, log_level="info")
