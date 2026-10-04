"""RAG Knowledge Service coordinating retrieval and Mistral synthesis."""

import logging
from typing import Optional
from rag_knowledge.retriever import KnowledgeRetriever
from rag_knowledge.mistral_client import MistralRAGClient

logger = logging.getLogger("rag.service")


class RAGService:
    """High-level service for knowledge retrieval and LLM synthesis."""

    def __init__(
        self,
        retriever: Optional[KnowledgeRetriever] = None,
        mistral_client: Optional[MistralRAGClient] = None,
    ):
        self.retriever = retriever or KnowledgeRetriever()
        self.mistral_client = mistral_client or MistralRAGClient()

    async def query(self, user_query: str) -> str:
        """Processes a user question, retrieves relevant facts, and synthesizes an answer.

        Args:
            user_query: The question asked by user (e.g. 'Do you know about Raj Ojha?').

        Returns:
            Grounded answer string ready for voice output.
        """
        clean_q = (user_query or "").strip()
        if not clean_q:
            return "Please specify what you would like to know about."

        # 1. Retrieve relevant knowledge documents
        results = self.retriever.retrieve(clean_q, top_k=2)
        if not results:
            logger.info(f"No RAG results found for query: '{clean_q}'")
            return f"I don't have specific details on '{clean_q}' in my knowledge base right now."

        top_doc = results[0]
        logger.info(f"Retrieved top match: '{top_doc.get('title')}' (score={top_doc.get('score')})")

        # 2. Build reference context
        context_parts = []
        for doc in results:
            context_parts.append(f"Title: {doc.get('title')}\nDetails: {doc.get('content')}")
        context = "\n\n".join(context_parts)

        # 3. Attempt Mistral API synthesis if available
        if self.mistral_client.is_configured:
            answer = await self.mistral_client.generate_answer(clean_q, context)
            if answer:
                return answer

        # 4. Seamless Fallback: Return structured factual summary directly
        # Designed specifically for natural voice output
        content = top_doc.get("content", "")
        summary = top_doc.get("summary", "")
        return content or summary


# Global default instance
_default_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _default_service
    if _default_service is None:
        _default_service = RAGService()
    return _default_service


async def query_rag(query: str) -> str:
    """Convenience helper function to query RAG knowledge base."""
    service = get_rag_service()
    return await service.query(query)
