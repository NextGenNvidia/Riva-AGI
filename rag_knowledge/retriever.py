"""Retriever module for rag_knowledge.

Performs database-driven search over structured knowledge documents stored
in MongoDB (riva_knowledge.knowledge_documents).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from rag_knowledge.storage.mongo import MongoKnowledgeStore, get_global_mongo_store

logger = logging.getLogger("rag.retriever")


class KnowledgeRetriever:
    """Database-backed knowledge retriever for RAG queries using MongoDB."""

    def __init__(self, store: Optional[MongoKnowledgeStore] = None) -> None:
        self.store: MongoKnowledgeStore = store or get_global_mongo_store()

    @property
    def documents(self) -> List[Dict[str, Any]]:
        """Lists active knowledge documents from MongoDB."""
        return self.store.list_documents()

    def retrieve(self, query: str, top_k: int = 2, min_score: float = 1.5) -> List[Dict[str, Any]]:
        """Retrieves top_k relevant documents from MongoDB for the given query.

        Args:
            query: The user query string (e.g. 'Who is Alex Doe?').
            top_k: Maximum number of relevant documents to return.
            min_score: Minimum relevance score required to be considered a match.

        Returns:
            List of matching document dicts with 'id', 'title', 'summary', 'content', and 'score'.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        try:
            return self.store.search_text(clean_query, top_k=top_k, min_score=min_score)
        except Exception as e:
            logger.error("Error retrieving knowledge from MongoDB for '%s': %s", clean_query, e, exc_info=True)
            return []

    def build_context_string(self, query: str, top_k: int = 2) -> str:
        """Convenience method to retrieve and format context into a clean text block."""
        results = self.retrieve(query, top_k=top_k)
        if not results:
            return ""

        context_parts = []
        for r in results:
            context_parts.append(f"[{r.get('title')}]\n{r.get('content')}")
        return "\n\n".join(context_parts)
