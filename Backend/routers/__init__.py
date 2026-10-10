"""Routers package for Riva-AGI Backend."""

from .web import router as web_router
from .voice import router as voice_router
from .chat import router as chat_router
from .agents import router as agents_router
from .tasks import router as tasks_router
from .system import router as system_router
from .rag import router as rag_router

__all__ = [
    "web_router",
    "voice_router",
    "chat_router",
    "agents_router",
    "tasks_router",
    "system_router",
    "rag_router",
]
