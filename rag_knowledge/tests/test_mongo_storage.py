"""Unit tests for MongoDB storage backend and retriever."""

import time
from unittest.mock import MagicMock, patch
import pytest

from rag_knowledge.storage.mongo import MongoKnowledgeStore, _ensure_dns_resolvers
from rag_knowledge.retriever import KnowledgeRetriever


def test_mongo_store_not_configured():
    """MongoKnowledgeStore returns is_available() False when URI is unset."""
    store = MongoKnowledgeStore(uri="")
    assert store.is_available() is False
    assert store.search_text("alex-doe") == []
    assert store.list_documents() == []


def test_mongo_store_mocked_success():
    """Verifies index creation, upsert, list_documents, and text search when MongoDB is connected."""
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_collection

    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_client.admin.command.return_value = {"ok": 1}

    # Simulate search results
    sample_doc = {
        "_id": "test_member",
        "id": "test_member",
        "title": "Alex Doe - AI Specialist",
        "summary": "Specialist in machine learning",
        "content": "TYPE: PERSON\nName: Alex Doe",
        "score": 4.5,
    }
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = [sample_doc]
    mock_collection.find.return_value = mock_cursor

    with patch("rag_knowledge.storage.mongo.MongoClient", return_value=mock_client):
        store = MongoKnowledgeStore(uri="mongodb://localhost:27017")
        assert store.connect() is True
        assert store.is_available() is True

        store.ensure_indexes()
        assert mock_collection.create_index.call_count >= 2

        count = store.upsert_documents([{"id": "test_member", "title": "Alex Doe"}])
        assert count == 1
        assert mock_collection.update_one.called

        # Test search
        results = store.search_text("machine learning")
        assert len(results) == 1
        assert results[0]["id"] == "test_member"
        assert results[0]["score"] == 4.5

        # Test list_documents
        docs = store.list_documents()
        assert len(docs) == 1

        store.close()
        assert store.is_available() is False


def test_mongo_upsert_document_with_is_active():
    """Verifies that upserting a document with 'is_active' does not cause a path conflict."""
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_client.admin.command.return_value = {"ok": 1}

    with patch("rag_knowledge.storage.mongo.MongoClient", return_value=mock_client):
        store = MongoKnowledgeStore(uri="mongodb://localhost:27017")
        store.connect()

        # Document explicitly containing is_active
        doc = {
            "id": "member_alex",
            "title": "Alex Doe",
            "is_active": True,
        }
        store.upsert_documents([doc])

        call_args = mock_collection.update_one.call_args[0]
        update_arg = call_args[1]
        # $set should contain is_active
        assert "$set" in update_arg
        assert update_arg["$set"]["is_active"] is True
        # $setOnInsert must NOT contain is_active to prevent MongoDB path conflict
        assert "$setOnInsert" not in update_arg or "is_active" not in update_arg["$setOnInsert"]


def test_mongo_cooldown_window():
    """Verifies that failed connect enters cooldown and skips repeated ping attempts."""
    mock_client = MagicMock()
    mock_client.admin.command.side_effect = ConnectionError("Mongo unreachable")

    with patch("rag_knowledge.storage.mongo.MongoClient", return_value=mock_client) as mock_mongo_cls:
        store = MongoKnowledgeStore(uri="mongodb://localhost:27017")
        # First attempt fails
        assert store.connect() is False
        assert mock_mongo_cls.call_count == 1

        # Second immediate attempt should be short-circuited by cooldown without calling MongoClient
        assert store.connect() is False
        assert mock_mongo_cls.call_count == 1


def test_ensure_dns_resolvers_opt_out(monkeypatch):
    """Verifies MONGODB_DISABLE_DNS_OVERRIDE and MONGODB_DNS_FALLBACK skip DNS mutation."""
    monkeypatch.setenv("MONGODB_DISABLE_DNS_OVERRIDE", "1")
    # Calling _ensure_dns_resolvers should immediately return without importing or modifying dns.resolver
    with patch("dns.resolver.get_default_resolver") as mock_resolver:
        _ensure_dns_resolvers()
        mock_resolver.assert_not_called()

    monkeypatch.delenv("MONGODB_DISABLE_DNS_OVERRIDE")
    monkeypatch.setenv("MONGODB_DNS_FALLBACK", "0")
    with patch("dns.resolver.get_default_resolver") as mock_resolver:
        _ensure_dns_resolvers()
        mock_resolver.assert_not_called()


def test_retriever_returns_empty_when_no_match():
    """KnowledgeRetriever returns empty list when query produces no match."""
    mock_store = MagicMock()
    mock_store.search_text.return_value = []

    retriever = KnowledgeRetriever(store=mock_store)
    results = retriever.retrieve("unknown query")
    assert results == []


def test_retriever_uses_mongo_when_available():
    """KnowledgeRetriever returns MongoDB results when available."""
    fake_mongo_result = [
        {
            "id": "custom_mongo_id",
            "title": "Mongo Custom Title",
            "summary": "From MongoDB cluster",
            "content": "Content from MongoDB",
            "score": 5.0,
        }
    ]

    mock_store = MagicMock()
    mock_store.is_available.return_value = True
    mock_store.search_text.return_value = fake_mongo_result

    retriever = KnowledgeRetriever(store=mock_store)
    results = retriever.retrieve("query")
    assert len(results) == 1
    assert results[0]["title"] == "Mongo Custom Title"
