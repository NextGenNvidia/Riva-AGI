"""Tests for RAGService in rag_knowledge."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from rag_knowledge.service import RAGService, query_rag, get_rag_service
from rag_knowledge.retriever import KnowledgeRetriever
from rag_knowledge.gemini_client import GeminiRAGClient


@pytest.mark.anyio
async def test_service_query_empty():
    mock_retriever = MagicMock()
    service = RAGService(retriever=mock_retriever)
    res = await service.query("")
    assert "Please specify" in res


@pytest.mark.anyio
async def test_service_query_not_found():
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []
    mock_retriever.store.is_available.return_value = True
    service = RAGService(retriever=mock_retriever)
    res = await service.query("xyzunknownterm9999")
    assert "I don't have specific details" in res


@pytest.mark.anyio
async def test_service_query_db_unavailable():
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []
    mock_retriever.store.is_available.return_value = False
    service = RAGService(retriever=mock_retriever)
    res = await service.query("Who is Alex Doe?")
    assert "database is currently unavailable" in res


@pytest.mark.anyio
async def test_service_query_fallback():
    # Gemini unconfigured -> fallback directly to retrieved facts
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [
        {
            "id": "alex-doe",
            "title": "Alex Doe",
            "summary": "Alex Doe is an AI systems architect focusing on modular speech systems.",
            "content": "Alex Doe is an AI systems architect focusing on modular speech systems.",
            "score": 4.5,
        }
    ]
    service = RAGService(
        retriever=mock_retriever,
        llm_client=GeminiRAGClient(api_key=""),
    )
    res = await service.query("Who is Alex Doe?")
    assert "Alex Doe" in res
    assert "systems architect" in res


@pytest.mark.anyio
async def test_service_query_with_gemini():
    mock_llm = MagicMock(spec=GeminiRAGClient)
    mock_llm.is_configured = True
    mock_llm.generate_answer = AsyncMock(
        return_value="Alex Doe is an AI systems architect at Riva."
    )
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [
        {
            "id": "alex-doe",
            "title": "Alex Doe",
            "summary": "Alex Doe is an AI researcher at Riva.",
            "content": "Alex Doe details",
            "score": 4.0,
        }
    ]

    service = RAGService(retriever=mock_retriever, llm_client=mock_llm)
    answer = await service.query("Do you know Alex Doe?")
    assert answer == "Alex Doe is an AI systems architect at Riva."
    mock_llm.generate_answer.assert_awaited_once()


@pytest.mark.anyio
async def test_global_query_rag_helper(monkeypatch):
    mock_retriever = MagicMock()
    mock_retriever.store.is_available.return_value = True
    mock_retriever.retrieve.return_value = [
        {
            "id": "alex-doe",
            "title": "Alex Doe",
            "summary": "Alex Doe is an AI researcher at Riva.",
            "content": "Alex Doe details",
            "score": 4.0,
        }
    ]
    mock_service = RAGService(retriever=mock_retriever, llm_client=GeminiRAGClient(api_key=""))
    monkeypatch.setattr("rag_knowledge.service.get_rag_service", lambda: mock_service)
    res = await query_rag("Who is Alex Doe?")
    assert "Alex Doe" in res
