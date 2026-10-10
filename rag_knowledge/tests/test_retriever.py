"""Tests for the database-backed KnowledgeRetriever class in rag_knowledge."""

from unittest.mock import MagicMock
import pytest
from rag_knowledge.retriever import KnowledgeRetriever
from rag_knowledge.storage.mongo import MongoKnowledgeStore


def test_retrieve_empty_query():
    mock_store = MagicMock(spec=MongoKnowledgeStore)
    retriever = KnowledgeRetriever(store=mock_store)
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []
    mock_store.search_text.assert_not_called()


def test_retriever_delegates_to_store():
    mock_store = MagicMock(spec=MongoKnowledgeStore)
    sample_docs = [
        {
            "id": "member_1",
            "title": "Member One",
            "summary": "Summary 1",
            "content": "Content 1",
            "score": 10.0,
        }
    ]
    mock_store.search_text.return_value = sample_docs
    mock_store.list_documents.return_value = sample_docs

    retriever = KnowledgeRetriever(store=mock_store)

    # Test retrieve()
    results = retriever.retrieve("Member One", top_k=2, min_score=3.0)
    mock_store.search_text.assert_called_once_with("Member One", top_k=2, min_score=3.0)
    assert len(results) == 1
    assert results[0]["id"] == "member_1"

    # Test documents property
    docs = retriever.documents
    mock_store.list_documents.assert_called_once()
    assert len(docs) == 1
    assert docs[0]["id"] == "member_1"


def test_build_context_string():
    mock_store = MagicMock(spec=MongoKnowledgeStore)
    mock_store.search_text.return_value = [
        {"title": "Doc A", "content": "Details A"},
        {"title": "Doc B", "content": "Details B"},
    ]

    retriever = KnowledgeRetriever(store=mock_store)
    context = retriever.build_context_string("query")
    assert "[Doc A]\nDetails A" in context
    assert "[Doc B]\nDetails B" in context


def test_build_context_string_empty():
    mock_store = MagicMock(spec=MongoKnowledgeStore)
    mock_store.search_text.return_value = []

    retriever = KnowledgeRetriever(store=mock_store)
    context = retriever.build_context_string("unknown")
    assert context == ""


def test_retrieve_error_handling():
    mock_store = MagicMock(spec=MongoKnowledgeStore)
    mock_store.search_text.side_effect = RuntimeError("Database timeout")

    retriever = KnowledgeRetriever(store=mock_store)
    results = retriever.retrieve("error query")
    assert results == []
