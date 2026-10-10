"""Riva-AGI Central Backend Application Server.

Coordinates multi-agent orchestration, real-time voice streaming gateway,
RAG knowledge retrieval, and system telemetry under a unified FastAPI server.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from fastapi import FastAPI
from Backend.config import config
from Backend.middleware.cors import setup_cors
from Backend.middleware.logging import RequestTimingMiddleware
from Backend.routers import (
    agents_router,
    chat_router,
    rag_router,
    system_router,
    tasks_router,
    voice_router,
    web_router,
)
from Backend.services.voice_service import voice_service

# Configure root logger
logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("riva.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for server boot and graceful shutdown."""
    logger.info("===============================================================")
    logger.info("  Riva-AGI Central Backend Server Initializing...")
    logger.info("  Host: %s:%d", config.host, config.port)
    logger.info("  Voice Service: %s", "Configured" if voice_service.is_configured() else "Degraded (No API Key)")
    logger.info("  Web UI Directory: %s", config.web_dir)
    logger.info("===============================================================")
    yield
    logger.info("Riva-AGI Central Backend Server shutting down...")


TAGS_METADATA = [
    {
        "name": "API Root",
        "description": "Server health status, endpoint directory, and metadata.",
    },
    {
        "name": "Chat & Multi-Agent Orchestration",
        "description": "Synchronous REST task execution (`/api/chat`) and real-time streaming WebSocket (`/api/chat/stream`) with RAG context.",
    },
    {
        "name": "Voice & Speech Gateway",
        "description": "Real-time bidirectional PCM16 audio bridge (`/ws`) connected to Google Gemini Live API and gateway telemetry.",
    },
    {
        "name": "Agent Registry",
        "description": "Directory of registered agents (`coder`, `researcher`, etc.), capabilities, and assigned tools.",
    },
    {
        "name": "Task State Tracking",
        "description": "Persistent task execution status, active agent owner, and step history.",
    },
    {
        "name": "RAG Knowledge Base",
        "description": "Vector retrieval and grounded answer synthesis from the knowledge repository.",
    },
    {
        "name": "System & Metrics",
        "description": "System hardware metrics (CPU, RAM, GPU, Battery) and subsystem availability.",
    },
    {
        "name": "Web UI",
        "description": "Browser-based client single-page application and AudioWorklet processor.",
    },
]

API_DESCRIPTION = """
# Riva-AGI Central Backend Application Server

Unified REST and WebSocket API gateway for the **Riva-AGI** autonomous cognitive platform.

## Subsystems
- **Real-Time Voice Streaming Gateway**: Bidirectional audio streaming over WebSocket (`/ws`) connected to Google Gemini Live API.
- **Multi-Agent Orchestration**: Intent recognition, DAG planner, executor, and specialized workers (`/api/chat`, `/api/chat/stream`).
- **Agent Registry**: Dynamic introspection of registered agents, tool sets, and hierarchy (`/api/agents/list`).
- **Task State Tracking**: Lifecycle states, step-by-step history, and transitions (`/api/tasks/{task_id}`).
- **RAG Knowledge Base**: High-performance grounded context retrieval and direct query synthesis (`/api/rag/query`).
- **System Telemetry**: Real-time hardware telemetry including CPU, RAM, Battery, and GPU (`/api/system/metrics`).

## WebSocket Streaming Endpoints
*Note: WebSockets are documented below as Starlette/FastAPI WebSockets are not listed in standard OpenAPI REST tables:*
- **`WS /ws`**: Browser Web Audio PCM16 stream with query parameters `?voice=Aoede&language=auto`.
- **`WS /api/chat/stream`**: Real-time streaming WebSocket emitting incremental agent tokens and execution metadata.

"""

# Initialize central FastAPI application
app = FastAPI(
    title="Riva-AGI Central Backend",
    description=API_DESCRIPTION,
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

# Attach Middlewares
setup_cors(app)
app.add_middleware(RequestTimingMiddleware)

# Include Subsystem Routers
# 1. Static Web UI Routes (/, /app.js, /worklet.js, /favicon.ico)
app.include_router(web_router)

# 2. Real-Time Voice Gateway (/ws and /api/voice/status)
app.include_router(voice_router)

# 3. Chat & Agent Orchestration (/api/chat, /api/chat/stream)
app.include_router(chat_router, prefix="/api/chat")

# 4. Agent Registry (/api/agents/list)
app.include_router(agents_router, prefix="/api/agents")

# 5. Task State Tracking (/api/tasks/{task_id})
app.include_router(tasks_router, prefix="/api/tasks")

# 6. System Health & Hardware Telemetry (/api/system/health, /api/system/metrics)
app.include_router(system_router, prefix="/api/system")

# 7. RAG Knowledge Base (/api/rag/query)
app.include_router(rag_router, prefix="/api/rag")




@app.get("/api", tags=["API Root"])
async def api_info():
    """Returns endpoint directory and server metadata."""
    return {
        "service": "Riva-AGI Central Backend",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "web_ui": "GET /",
            "voice_gateway": "WS /ws",
            "voice_status": "GET /api/voice/status",
            "chat_rest": "POST /api/chat",
            "chat_stream": "WS /api/chat/stream",
            "agents_list": "GET /api/agents/list",
            "tasks_status": "GET /api/tasks/{task_id}",
            "system_health": "GET /api/system/health",
            "system_metrics": "GET /api/system/metrics",
            "rag_query": "POST /api/rag/query",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "Backend.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=False,
    )
