"""RAG Knowledge Base request and response models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """Request payload for direct RAG knowledge query."""
    query: str = Field(..., description="Query string to search knowledge base.")
    top_k: Optional[int] = Field(2, description="Maximum number of relevant documents to retrieve.")


class SourceDocument(BaseModel):
    """Schema for retrieved reference sources."""
    title: str = Field(..., description="Title or source of the retrieved knowledge document.")
    score: float = Field(0.0, description="Relevance score of the match.")
    summary: Optional[str] = Field(None, description="Extracted summary of the document.")


class RAGQueryResponse(BaseModel):
    """Response payload containing synthesized answer and sources."""
    answer: str = Field(..., description="Grounded answer synthesized from knowledge base.")
    sources: List[SourceDocument] = Field(default_factory=list, description="List of source matches retrieved.")
