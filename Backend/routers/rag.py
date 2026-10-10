"""RAG Knowledge Base Query Router."""

import logging
from fastapi import APIRouter

from Backend.models.rag import RAGQueryRequest, RAGQueryResponse, SourceDocument
from Backend.services.rag_service import rag_service

logger = logging.getLogger("riva.backend.routers.rag")

router = APIRouter(tags=["RAG Knowledge Base"])


@router.post("/query", response_model=RAGQueryResponse, summary="Query Knowledge Base")
async def query_knowledge_base(request: RAGQueryRequest) -> RAGQueryResponse:
    """Queries the RAG knowledge store directly and returns synthesized answers with citations."""
    top_k = request.top_k or 2
    result = await rag_service.direct_query(query_str=request.query, top_k=top_k)

    sources = [
        SourceDocument(
            title=s.get("title", "Untitled Document"),
            score=float(s.get("score", 0.0)),
            summary=s.get("summary"),
        )
        for s in result.get("sources", [])
    ]

    return RAGQueryResponse(
        answer=result.get("answer", ""),
        sources=sources,
    )
