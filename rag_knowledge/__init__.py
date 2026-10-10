"""RAG Knowledge Package for Riva Voice Assistant.

Provides modular knowledge retrieval and Google Gemini synthesis.
"""

import os
from pathlib import Path


def load_env() -> None:
    """Loads environment variables from package .env or project root .env.

    Prefers python-dotenv if installed, otherwise parses key-value pairs safely.
    """
    env_paths = [
        Path(__file__).resolve().parent / ".env",
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
                            # Handle quoted values
                            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                                val = val[1:-1]
                            elif " #" in val:
                                # Strip trailing comment only when preceded by whitespace
                                val = val.split(" #", 1)[0].strip()
                            if key and key not in os.environ:
                                os.environ[key] = val
            except Exception:
                pass


from rag_knowledge.retriever import KnowledgeRetriever
from rag_knowledge.gemini_client import GeminiRAGClient
from rag_knowledge.service import RAGService, query_rag, get_rag_service
from rag_knowledge.storage.mongo import MongoKnowledgeStore

__all__ = [
    "KnowledgeRetriever",
    "GeminiRAGClient",
    "RAGService",
    "query_rag",
    "get_rag_service",
    "MongoKnowledgeStore",
    "load_env",
]

