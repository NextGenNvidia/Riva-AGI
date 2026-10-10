"""Pydantic data models for request/response schemas in Riva-AGI Backend."""

from .chat import ChatRequest, ChatResponse
from .agents import AgentItem, AgentsListResponse
from .tasks import TaskStatusResponse
from .system import HealthResponse, MetricsResponse, ServiceStatuses
from .voice import VoiceStatusResponse
from .rag import RAGQueryRequest, RAGQueryResponse, SourceDocument

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "AgentItem",
    "AgentsListResponse",
    "TaskStatusResponse",
    "HealthResponse",
    "MetricsResponse",
    "ServiceStatuses",
    "VoiceStatusResponse",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "SourceDocument",
]
