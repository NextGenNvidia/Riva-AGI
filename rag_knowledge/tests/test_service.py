"""Tests for RAGService in rag_knowledge."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from rag_knowledge.service import RAGService, query_rag, get_rag_service
from rag_knowledge.retriever import KnowledgeRetriever
from rag_knowledge.mistral_client import MistralRAGClient


@pytest.mark.anyio
async def test_service_query_empty():
    service = RAGService()
    res = await service.query("")
    assert "Please specify" in res


@pytest.mark.anyio
async def test_service_query_not_found():
    service = RAGService()
    res = await service.query("xyzunknownterm9999")
    assert "I don't have specific details" in res


@pytest.mark.anyio
async def test_service_query_fallback():
    # Mistral unconfigured -> fallback directly to retrieved facts
    service = RAGService(mistral_client=MistralRAGClient(api_key=""))
    res = await service.query("Who is Raj Ojha?")
    assert "Raj Ojha" in res
    assert "NextGen SuperComputing Club" in res


@pytest.mark.anyio
async def test_service_query_with_mistral():
    mock_mistral = MagicMock(spec=MistralRAGClient)
    mock_mistral.is_configured = True
    mock_mistral.generate_answer = AsyncMock(
        return_value="Raj Ojha is an AI systems architect at KIET."
    )

    service = RAGService(mistral_client=mock_mistral)
    answer = await service.query("Do you know Raj Ojha?")
    assert answer == "Raj Ojha is an AI systems architect at KIET."
    mock_mistral.generate_answer.assert_awaited_once()


@pytest.mark.anyio
async def test_global_query_rag_helper():
    res = await query_rag("Who is Raj Ojha?")
    assert "Raj Ojha" in res
