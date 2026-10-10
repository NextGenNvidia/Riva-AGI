"""Web Router serving the browser-based Voice Interface UI.

Provides static endpoints for the HTML client, AudioWorklet processor,
and supporting assets formerly hosted in voice_speech/web_server.py.
"""

import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
from Backend.config import config

router = APIRouter(tags=["Web UI"])

INDEX_PATH = config.web_dir / "index.html"
APP_JS_PATH = config.web_dir / "app.js"
WORKLET_JS_PATH = config.web_dir / "worklet.js"


@router.get("/", summary="Voice Interface Web Application")
async def get_index():
    """Serves the main single-page voice interface HTML."""
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH)
    return {"message": "Riva Voice Web UI (index.html not found)", "path": str(INDEX_PATH)}


@router.get("/app.js", summary="Voice Interface Client Script")
async def get_app_js():
    """Serves the main client-side JavaScript file."""
    if APP_JS_PATH.exists():
        return FileResponse(APP_JS_PATH)
    return Response(content="// app.js not found", media_type="application/javascript")


@router.get("/worklet.js", summary="AudioWorklet Processor Script")
async def get_worklet_js():
    """Serves the custom Web Audio PCM16 AudioWorklet processor."""
    if WORKLET_JS_PATH.exists():
        return FileResponse(WORKLET_JS_PATH)
    return Response(content="// worklet.js not found", media_type="application/javascript")


@router.get("/favicon.ico", summary="Application Favicon")
async def get_favicon():
    """Returns SVG favicon for browser tabs."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#4dbc1b"/></svg>'
    return Response(content=svg, media_type="image/svg+xml")
