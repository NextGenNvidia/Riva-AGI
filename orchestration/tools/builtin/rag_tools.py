"""
RAG Knowledge Base Agent Tools for Riva-AGI.
===========================================
Bridges the Qdrant-powered rag_knowledge subsystem into the autonomous agent
tool loop, allowing agents (e.g. researcher, coder) to query documents and cite sources.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

from orchestration.tools.registry import tool

logger = logging.getLogger("orchestration.tools.rag")


def _get_retriever():
    """Lazily imports and instantiates the KnowledgeRetriever."""
    try:
        from rag_knowledge.retrieval.retriever import KnowledgeRetriever
        return KnowledgeRetriever()
    except Exception as e:
        logger.warning(f"Could not initialize KnowledgeRetriever: {e}")
        return None


def _get_rag_service():
    """Lazily imports and instantiates the RAGService."""
    try:
        from rag_knowledge.service import get_rag_service
        return get_rag_service()
    except Exception as e:
        logger.warning(f"Could not initialize RAGService: {e}")
        return None


@tool(category="knowledge")
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """Searches the Qdrant vector knowledge base for relevant document chunks matching a query.

    Args:
        query: The semantic search query (e.g. 'What is the schedule for ComputeX?' or 'internal guidelines').
        top_k: Maximum number of relevant document chunks to return (default: 5).

    Returns:
        Structured string containing matching document titles, relevance scores, cited sources, and content.
    """
    clean_q = (query or "").strip()
    if not clean_q:
        return "Please provide a non-empty search query."

    retriever = _get_retriever()
    if not retriever:
        return "Knowledge base retriever is not available on this system."

    try:
        results = retriever.retrieve(clean_q, top_k=top_k)
    except Exception as exc:
        logger.error(f"Error during RAG retrieval: {exc}")
        return f"Knowledge base query error: {exc}"

    if not results:
        return f"No relevant documents found in knowledge base for query: '{clean_q}'."

    output_lines = [f"Found {len(results)} relevant knowledge chunks for query: '{clean_q}':\n"]
    for i, doc in enumerate(results, start=1):
        title = doc.get("title", "Untitled Document")
        score = doc.get("score", 0.0)
        content = doc.get("content", "").strip()
        meta = doc.get("metadata") or {}
        source = meta.get("source") or meta.get("source_file") or "Internal"
        page = meta.get("page") if meta.get("page") is not None else meta.get("page_number")
        page_str = f", Page {page}" if page is not None else ""

        output_lines.append(f"{i}. [{title}] (Score: {score:.2f} | Source: {source}{page_str})")
        output_lines.append(f"   Excerpt: {content[:400]}...\n" if len(content) > 400 else f"   Excerpt: {content}\n")

    return "\n".join(output_lines)


@tool(category="knowledge")
def query_knowledge_with_citations(query: str) -> str:
    """Queries the knowledge base and synthesizes a grounded answer with precise source citations.

    Args:
        query: The user question to answer from indexed documents.

    Returns:
        Grounded answer with explicit source files and page numbers cited.
    """
    clean_q = (query or "").strip()
    if not clean_q:
        return "Please provide a non-empty question."

    service = _get_rag_service()
    if not service:
        return "RAG Knowledge Service is not available on this system."

    try:
        # Run async query_with_sources in synchronous tool execution context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                answer, sources = pool.submit(asyncio.run, service.query_with_sources(clean_q)).result()
        else:
            answer, sources = asyncio.run(service.query_with_sources(clean_q))

        citations_str = "\n".join(f"  • {s}" for s in sources) if sources else "  • No explicit file citations"
        return f"Answer:\n{answer}\n\nCited Sources:\n{citations_str}"
    except Exception as exc:
        logger.error(f"Error querying knowledge service: {exc}")
        return f"Error querying knowledge base: {exc}"


@tool(category="knowledge")
def list_knowledge_documents() -> str:
    """Lists indexed documents and collections currently stored in the vector knowledge base.

    Returns:
        JSON string listing document IDs, titles, categories, and source filenames.
    """
    retriever = _get_retriever()
    if not retriever:
        return "Knowledge base retriever is not available on this system."

    try:
        docs = retriever.documents
        if not docs:
            return "Knowledge base is currently empty or vector database is not connected."

        summary_list = []
        for d in docs:
            meta = d.get("metadata") or {}
            summary_list.append({
                "id": d.get("id"),
                "title": d.get("title", "Untitled"),
                "category": d.get("category", "general"),
                "source": meta.get("source") or meta.get("source_file") or "Internal",
            })
        return json.dumps(summary_list, indent=2)
    except Exception as exc:
        logger.error(f"Error listing knowledge documents: {exc}")
        return f"Error retrieving document list: {exc}"


@tool(category="knowledge")
def ingest_document_to_knowledge_base(file_path: str, data_type: str = "auto") -> str:
    """Ingests a local document (.pdf, .docx, or text) into the Qdrant vector knowledge base after privacy scanning.

    Args:
        file_path: Path to the document on the local filesystem.
        data_type: Document parser type: 'auto' (default), 'pdf', or 'word'.

    Returns:
        Confirmation of chunking, privacy validation, and vector database upsert.
    """
    path_obj = Path(file_path).resolve()
    if not path_obj.exists() or not path_obj.is_file():
        return f"File does not exist: {file_path}"

    try:
        from rag_knowledge.ingestion.pipeline import run_ingestion
        count = run_ingestion(
            source_dir=path_obj,
            data_type=data_type,
            allow_cloud_vision=False,
            redact=True,
        )
        return (
            f"Successfully ingested '{path_obj.name}' into knowledge base. "
            f"Indexed {count} documents into Qdrant collection."
        )
    except Exception as exc:
        logger.error(f"Error ingesting document '{file_path}': {exc}")
        return f"Document ingestion failed: {exc}"
