"""RAG Knowledge Package for Riva Voice Assistant.

Provides modular knowledge retrieval and Google Gemini synthesis.
"""

import os
from pathlib import Path


def load_env() -> None:
    """Load environment variables from package or root .env file."""
    if os.getenv("RAG_DISABLE_LOAD_ENV", "").lower() in ("true", "1", "yes"):
        return

    env_paths = [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    if os.getenv("RAG_LOAD_CWD_ENV", "").lower() in ("true", "1", "yes"):
        env_paths.insert(0, Path.cwd() / ".env")

    for p in env_paths:
        if p.is_file():
            try:
                try:
                    from dotenv import load_dotenv
                    load_dotenv(dotenv_path=p, override=False)
                    continue
                except ImportError:
                    pass

                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("export "):
                            line = line[7:].strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            key = k.strip()
                            val = v.strip()
                            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                                val = val[1:-1]
                            elif " #" in val:
                                val = val.split(" #", 1)[0].strip()
                            if key and key not in os.environ:
                                os.environ[key] = val
            except Exception:
                pass


from .retrieval.retriever import KnowledgeRetriever, RetrievalError
from .clients.gemini_client import GeminiRAGClient
from .service import RAGService, query_rag, get_rag_service
from .storage.qdrant_storage import QdrantKnowledgeStore
from . import clients, ingestion, prompts, retrieval, service, storage
from .retrieval import retriever
from .clients import gemini_client
from .ingestion import ingest

__all__ = [
    "KnowledgeRetriever",
    "RetrievalError",
    "GeminiRAGClient",
    "RAGService",
    "query_rag",
    "get_rag_service",
    "QdrantKnowledgeStore",
    "load_env",
    "clients",
    "ingestion",
    "retrieval",
    "storage",
    "prompts",
    "service",
    "retriever",
    "gemini_client",
    "ingest",
]
