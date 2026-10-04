"""Retriever module for rag_knowledge.

Performs keyword, title, and token-based semantic scoring over structured
knowledge documents stored in the rag_knowledge/data/ directory.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rag.retriever")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_JSON = os.path.join(DATA_DIR, "knowledge.json")


def _tokenize(text: str) -> List[str]:
    """Extracts lowercased alphanumeric word tokens."""
    return re.findall(r"\w+", (text or "").lower())


class KnowledgeRetriever:
    """In-memory fast knowledge retriever for RAG queries."""

    def __init__(self, data_file: Optional[str] = None):
        self.data_file = data_file or os.getenv("KNOWLEDGE_DATA_PATH", "").strip() or DEFAULT_JSON
        self.documents: List[Dict[str, Any]] = []
        self.load_data()

    def load_data(self) -> None:
        """Loads or reloads knowledge documents from JSON."""
        if not os.path.exists(self.data_file):
            logger.warning(f"Knowledge data file not found: {self.data_file}")
            self.documents = []
            return

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
            logger.info(f"Loaded {len(self.documents)} knowledge documents from {self.data_file}")
        except Exception as e:
            logger.error(f"Error loading knowledge data: {e}", exc_info=True)
            self.documents = []

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Scores and retrieves top_k relevant documents for the given query.

        Args:
            query: The user query string (e.g. 'do you know about Raj Ojha?').
            top_k: Maximum number of relevant documents to return.

        Returns:
            List of matching document dicts with 'score' and 'matched_keywords'.
        """
        if not self.documents:
            self.load_data()

        query_lower = query.lower().strip()
        query_tokens = set(_tokenize(query_lower))

        scored_docs = []
        for doc in self.documents:
            score = 0.0
            matched_kw = []

            # 1. Direct substring match on document title or keywords
            doc_title_lower = doc.get("title", "").lower()
            if any(term in query_lower for term in doc_title_lower.split(" - ")[0].split()):
                score += 5.0

            # 2. Check explicitly declared keywords/aliases
            for kw in doc.get("keywords", []):
                kw_lower = kw.lower()
                if kw_lower in query_lower:
                    score += 10.0
                    matched_kw.append(kw)
                elif any(q_tok == kw_lower for q_tok in query_tokens):
                    score += 6.0
                    matched_kw.append(kw)

            # 3. Content token overlap
            content_tokens = set(_tokenize(doc.get("content", "")))
            overlap = query_tokens.intersection(content_tokens)
            score += len(overlap) * 1.5

            if score > 0:
                scored_docs.append({
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "summary": doc.get("summary"),
                    "content": doc.get("content"),
                    "score": score,
                    "matched_keywords": matched_kw,
                })

        # Sort descending by relevance score
        scored_docs.sort(key=lambda d: d["score"], reverse=True)
        return scored_docs[:top_k]

    def build_context_string(self, query: str, top_k: int = 2) -> str:
        """Convenience method to retrieve and format context into a clean text block."""
        results = self.retrieve(query, top_k=top_k)
        if not results:
            return ""

        context_parts = []
        for r in results:
            context_parts.append(f"[{r['title']}]\n{r['content']}")
        return "\n\n".join(context_parts)
