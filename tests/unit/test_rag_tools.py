"""
Unit tests for RAG Knowledge Base Agent Tools.
==============================================
Validates the integration between rag_knowledge and the orchestration tool registry,
including search, grounded citation querying, document listing, and researcher capabilities.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from orchestration.tools import tool_registry
from orchestration.tools.builtin.rag_tools import (
    search_knowledge_base,
    query_knowledge_with_citations,
    list_knowledge_documents,
    ingest_document_to_knowledge_base,
)
from orchestration.orchestrator.registry import registry
from orchestration.orchestrator.router import classify_intent
import orchestration.agents.researcher


def test_rag_tools_registered_in_tool_registry():
    """Verify all RAG tools are properly registered with category 'knowledge'."""
    assert "search_knowledge_base" in tool_registry
    assert "query_knowledge_with_citations" in tool_registry
    assert "list_knowledge_documents" in tool_registry
    assert "ingest_document_to_knowledge_base" in tool_registry

    search_def = tool_registry.get_tool_definition("search_knowledge_base")
    assert search_def is not None
    assert search_def.category == "knowledge"
    assert "query" in search_def.parameters_schema

    cite_def = tool_registry.get_tool_definition("query_knowledge_with_citations")
    assert cite_def is not None
    assert cite_def.category == "knowledge"


def test_search_knowledge_base_success():
    """Verify search_knowledge_base formats retrieved document chunks with metadata."""
    fake_results = [
        {
            "id": "doc-001",
            "title": "ComputeX Event Schedule",
            "score": 0.88,
            "content": "Keynote begins at 10:00 AM in Hall A.",
            "metadata": {"source": "computex_schedule.pdf", "page": 1},
        },
        {
            "id": "doc-002",
            "title": "NVIDIA DGX Technical Specs",
            "score": 0.82,
            "content": "Powered by 8x NVIDIA H100 Tensor Core GPUs.",
            "metadata": {"source": "dgx_specs.docx", "page": 4},
        },
    ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = fake_results

    with patch("orchestration.tools.builtin.rag_tools._get_retriever", return_value=mock_retriever):
        output = search_knowledge_base("When is the keynote?")
        assert "Found 2 relevant knowledge chunks" in output
        assert "ComputeX Event Schedule" in output
        assert "computex_schedule.pdf, Page 1" in output
        assert "NVIDIA DGX Technical Specs" in output
        assert "Keynote begins at 10:00 AM" in output


def test_search_knowledge_base_empty():
    """Verify empty search results return a clean, user-friendly message."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []

    with patch("orchestration.tools.builtin.rag_tools._get_retriever", return_value=mock_retriever):
        output = search_knowledge_base("unknown topic query")
        assert "No relevant documents found" in output


def test_search_knowledge_base_empty_query():
    """Verify empty or whitespace query is rejected gracefully."""
    output = search_knowledge_base("   ")
    assert "Please provide a non-empty search query" in output


def test_query_knowledge_with_citations_success():
    """Verify query_knowledge_with_citations returns synthesis with cited sources."""
    mock_service = MagicMock()

    async def fake_query_with_sources(query):
        return ("The keynote begins at 10:00 AM in Hall A.", ["computex_schedule.pdf (Page 1)"])

    mock_service.query_with_sources.side_effect = fake_query_with_sources

    with patch("orchestration.tools.builtin.rag_tools._get_rag_service", return_value=mock_service):
        output = query_knowledge_with_citations("When is the keynote?")
        assert "Answer:" in output
        assert "The keynote begins at 10:00 AM" in output
        assert "Cited Sources:" in output
        assert "computex_schedule.pdf (Page 1)" in output


def test_list_knowledge_documents_success():
    """Verify list_knowledge_documents returns structured JSON document metadata."""
    fake_docs = [
        {
            "id": "doc-01",
            "title": "Riva-AGI Architecture",
            "category": "architecture",
            "metadata": {"source": "arch.pdf"},
        }
    ]

    mock_retriever = MagicMock()
    mock_retriever.documents = fake_docs

    with patch("orchestration.tools.builtin.rag_tools._get_retriever", return_value=mock_retriever):
        output = list_knowledge_documents()
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Riva-AGI Architecture"
        assert data[0]["source"] == "arch.pdf"


def test_ingest_document_to_knowledge_base_missing_file():
    """Verify ingestion errors when given a nonexistent file path."""
    output = ingest_document_to_knowledge_base("nonexistent_path/fake_doc.pdf")
    assert "File does not exist" in output


def test_ingest_document_to_knowledge_base_success(tmp_path):
    """Verify successful ingestion pipeline execution."""
    test_file = tmp_path / "sample.pdf"
    test_file.write_text("Dummy content for testing ingestion pipeline.")

    fake_result = {
        "status": "success",
        "chunks_upserted": 4,
        "collection": "riva_knowledge",
    }

    with patch("rag_knowledge.ingestion.pipeline.run_ingestion", return_value=4):
        output = ingest_document_to_knowledge_base(str(test_file))
        assert "Successfully ingested 'sample.pdf'" in output
        assert "4 documents" in output


def test_researcher_agent_capabilities_has_rag_tools():
    """Verify researcher agent is registered with RAG knowledge tools."""
    caps = registry.get_capabilities("researcher")
    assert caps is not None
    assert "search_knowledge_base" in caps.tools
    assert "query_knowledge_with_citations" in caps.tools
    assert "list_knowledge_documents" in caps.tools


def test_router_routes_rag_keywords_to_researcher():
    """Verify router matches knowledge base and documentation keywords to researcher."""
    result = classify_intent("Search the internal knowledge base for the event schedule and documentation guidelines")
    assert result["agent"] == "researcher"
    assert result["intent"] == "research"
