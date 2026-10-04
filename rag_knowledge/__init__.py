"""RAG Knowledge Package for Riva Voice Assistant.

Provides modular knowledge retrieval and Mistral AI synthesis.
"""

import os
from pathlib import Path


def _load_env_fallback() -> None:
    """Zero-dependency environment loader that reads .env from project root or package dir."""
    env_paths = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for p in env_paths:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            key = k.strip()
                            val = v.strip().strip("'\"")
                            if key and key not in os.environ:
                                os.environ[key] = val
            except Exception:
                pass


_load_env_fallback()

from rag_knowledge.retriever import KnowledgeRetriever
from rag_knowledge.mistral_client import MistralRAGClient
from rag_knowledge.service import RAGService, query_rag, get_rag_service

__all__ = [
    "KnowledgeRetriever",
    "MistralRAGClient",
    "RAGService",
    "query_rag",
    "get_rag_service",
]
