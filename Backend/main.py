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


# Initialize central FastAPI application
app = FastAPI(
    title="Riva-AGI Central Backend",
    description="Unified backend REST and WebSocket services for the Riva-AGI autonomous platform.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
        "docs_url": "/docs",
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
