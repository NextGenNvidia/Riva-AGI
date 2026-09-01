"""
Riva WebSocket Voice Gateway Server (FastAPI + Web Audio Worklet).
Clean, modular bridge routing between browser Web Audio and Gemini Live API.
"""

import logging
import os
import sys
from pathlib import Path

# Ensure parent directory is in sys.path for voice_speech package imports
_pkg_root = str(Path(__file__).resolve().parent.parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from voice_speech.engine.config.settings import Settings
from voice_speech.engine.conversation.session_manager import SessionManager
from voice_speech.engine.conversation.state import ConversationState
from voice_speech.engine.gemini.session import create_gemini_client
from voice_speech.engine.gemini.streaming import run_live_bridge

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("riva.web_server")

# Load unified settings
settings = Settings()

# Validate API key at startup (fail fast)
if not settings.gemini.api_key:
    logger.error(
        "GEMINI_API_KEY is not set! "
        "Copy voice_speech/.env.example to .env and add your key from https://aistudio.google.com/app/apikey"
    )
    sys.exit(1)

# Shared Gemini Live Client and Concurrency / Rate Limiting Session Manager
gemini_client = create_gemini_client(api_key=settings.gemini.api_key)
session_manager = SessionManager()

app = FastAPI(title="Riva Voice Gateway")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")


# Static Web UI Routes
@app.get("/")
async def get_index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/app.js")
async def get_app_js():
    return FileResponse(os.path.join(WEB_DIR, "app.js"))


@app.get("/worklet.js")
async def get_worklet_js():
    return FileResponse(os.path.join(WEB_DIR, "worklet.js"))


@app.get("/favicon.ico")
async def get_favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#4dbc1b"/></svg>'
    return Response(content=svg, media_type="image/svg+xml")


# Real-Time Bidirectional Voice WebSocket Endpoint
@app.websocket("/ws")
async def audio_websocket_endpoint(websocket: WebSocket):
    # 1. Origin validation (prevent unauthorized cross-origin WebSocket drain)
    origin = websocket.headers.get("origin", "")
    allowed_origins = {"http://localhost:8000", "http://localhost", "http://127.0.0.1:8000", "https://localhost:8000"}
    if origin and origin not in allowed_origins:
        logger.warning(f"Rejected WebSocket from unauthorized origin: {origin}")
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # 2. Concurrency & Circuit Breaker Admission
    acquired, error_msg = await session_manager.try_acquire()
    if not acquired:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": error_msg})
        await websocket.close(code=4029)
        return

    try:
        await websocket.accept()
    except Exception:
        await session_manager.release()
        return

    voice = websocket.query_params.get("voice") or "Aoede"
    language = websocket.query_params.get("language") or "auto"
    logger.info(
        f"Browser client connected to /ws (voice={voice}, language={language}) "
        f"[{session_manager.active_sessions}/{session_manager.max_concurrent_sessions} sessions]"
    )

    state = ConversationState()

    try:
        await run_live_bridge(
            client=gemini_client,
            websocket=websocket,
            settings=settings,
            state=state,
            session_mgr=session_manager,
            voice=voice,
            language=language,
        )
    except WebSocketDisconnect:
        logger.info("Browser client disconnected cleanly.")
    except Exception as e:
        logger.error(f"WebSocket bridge exception: {e}", exc_info=True)
    finally:
        state.terminate()
        await session_manager.release()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("voice_speech.web_server:app", host="0.0.0.0", port=port, log_level="info")
