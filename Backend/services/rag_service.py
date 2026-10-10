"""RAG Knowledge Service integration for Riva-AGI.

Coordinates knowledge base retrieval and synthesis, providing graceful degradation
when database connections are unavailable or timed out.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("riva.backend.rag_service")


class RAGServiceWrapper:
    """Provides resilient interaction with the RAG knowledge subsystem."""

    def __init__(self):
        self._service = None

    def get_service(self):
        """Lazy loader for RAG service to avoid unnecessary connection attempts on boot."""
        if self._service is None:
            try:
                from rag_knowledge.service import get_rag_service
                self._service = get_rag_service()
            except Exception as e:
                logger.warning(f"Failed to initialize RAG knowledge service: {e}")
                return None
        return self._service

    def get_health_status(self) -> Dict[str, str]:
        """Probes the health of the RAG retriever and MongoDB storage."""
        svc = self.get_service()
        if svc is None:
            return {"rag": "unavailable", "mongodb": "disconnected"}

        try:
            if hasattr(svc, "retriever") and hasattr(svc.retriever, "store"):
                is_connected = svc.retriever.store.is_available()
                return {
                    "rag": "connected" if is_connected else "ready",
                    "mongodb": "connected" if is_connected else "disconnected",
                }
        except Exception as e:
            logger.warning(f"Error checking RAG health: {e}")

        return {"rag": "degraded", "mongodb": "disconnected"}

    async def enrich_task_with_rag(self, message: str, timeout_seconds: float = 3.5) -> str:
        """Pre-fetches knowledge base context and prepends it to the user task if relevant."""
        svc = self.get_service()
        if not svc:
            return message

        try:
            from rag_knowledge.service import query_rag

            context = await asyncio.wait_for(query_rag(message), timeout=timeout_seconds)
            negative_markers = [
                "don't have specific details",
                "database is currently unavailable",
                "specify what you would like to know",
            ]
            if context and not any(marker in context.lower() for marker in negative_markers):
                logger.info("Enriched task with RAG context: %s...", context[:100])
                return f"Relevant Context from Knowledge Base:\n{context}\n\nUser Task:\n{message}"
        except asyncio.TimeoutError:
            logger.warning("RAG pre-fetch timed out (exceeded %.1fs); continuing without enrichment.", timeout_seconds)
        except Exception as e:
            logger.warning("Could not pre-fetch RAG context: %s", e)

        return message

    async def direct_query(self, query_str: str, top_k: int = 2) -> Dict[str, Any]:
        """Executes a direct RAG retrieval and synthesis."""
        svc = self.get_service()
        if not svc:
            return {
                "answer": "RAG knowledge base is currently unavailable.",
                "sources": [],
            }

        clean_query = query_str.strip()
        docs = await asyncio.to_thread(svc.retriever.retrieve, clean_query, top_k=top_k)
        answer = await svc.query(clean_query, pre_retrieved=docs)

        sources = []
        for doc in docs:
            sources.append({
                "title": doc.get("title", "Untitled Document"),
                "score": float(doc.get("score", 0.0)),
                "summary": doc.get("summary") or doc.get("content", "")[:200],
            })

        return {
            "answer": answer,
            "sources": sources,
        }


# Global singleton instance
rag_service = RAGServiceWrapper()
