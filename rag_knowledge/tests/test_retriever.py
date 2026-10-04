"""Tests for the KnowledgeRetriever class in rag_knowledge."""

import os
import tempfile
import json
import pytest
from rag_knowledge.retriever import KnowledgeRetriever, _tokenize


def test_tokenize():
    tokens = _tokenize("Hello, World! Who is Raj Ojha?")
    assert tokens == ["hello", "world", "who", "is", "raj", "ojha"]


def test_default_retriever_loading():
    retriever = KnowledgeRetriever()
    assert len(retriever.documents) >= 6
    doc_ids = [d["id"] for d in retriever.documents]
    assert "raj_ojha" in doc_ids
    assert "nextgen_club" in doc_ids
    assert "riva_project" in doc_ids
    assert "chirag_tejasvi" in doc_ids
    assert "ayush_pathak" in doc_ids
    assert "ankit_singh_tomar" in doc_ids


def test_retrieve_chirag_tejasvi():
    retriever = KnowledgeRetriever()
    results = retriever.retrieve("Tell me about Chirag Tejasvi and MuktiVerse", top_k=1)
    assert len(results) > 0
    assert results[0]["id"] == "chirag_tejasvi"


def test_retrieve_ayush_pathak():
    retriever = KnowledgeRetriever()
    results = retriever.retrieve("Who is Ayush Pathak working on IoT and ESP32?", top_k=1)
    assert len(results) > 0
    assert results[0]["id"] == "ayush_pathak"


def test_retrieve_ankit_singh_tomar():
    retriever = KnowledgeRetriever()
    results = retriever.retrieve("What has Ankit Singh Tomar developed at Noteboat?", top_k=1)
    assert len(results) > 0
    assert results[0]["id"] == "ankit_singh_tomar"



def test_retrieve_raj_ojha():
    retriever = KnowledgeRetriever()
    queries = [
        "Do you know about Raj Ojha?",
        "Who is Raj Ojha?",
        "Tell me about raj",
        "Who is the lead systems architect?",
    ]
    for q in queries:
        results = retriever.retrieve(q, top_k=1)
        assert len(results) > 0, f"Failed for query: {q}"
        assert results[0]["id"] == "raj_ojha", f"Expected raj_ojha for query: {q}"
        assert results[0]["score"] > 0


def test_retrieve_nextgen_club():
    retriever = KnowledgeRetriever()
    results = retriever.retrieve("What is NextGen SuperComputing Club at KIET?", top_k=1)
    assert len(results) > 0
    assert results[0]["id"] == "nextgen_club"


def test_retrieve_no_match():
    retriever = KnowledgeRetriever()
    results = retriever.retrieve("completely unrelated query 12345 xyz", top_k=2)
    assert len(results) == 0


def test_custom_data_file():
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False, encoding="utf-8") as tmp:
        sample_data = [
            {
                "id": "custom_agent",
                "title": "Quantum Agent X",
                "keywords": ["quantum", "agent", "x"],
                "summary": "A test agent.",
                "content": "Quantum Agent X is a specialized research unit."
            }
        ]
        json.dump(sample_data, tmp)
        tmp_path = tmp.name

    try:
        retriever = KnowledgeRetriever(data_file=tmp_path)
        assert len(retriever.documents) == 1
        results = retriever.retrieve("tell me about quantum agent", top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "custom_agent"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_dynamic_mtime_reloading():
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False, encoding="utf-8") as tmp:
        initial_data = [{"id": "doc1", "title": "Doc One", "keywords": ["doc1"], "summary": "s1", "content": "c1"}]
        json.dump(initial_data, tmp)
        tmp_path = tmp.name

    try:
        retriever = KnowledgeRetriever(data_file=tmp_path)
        assert len(retriever.documents) == 1

        # Simulate on-disk file update
        import time
        time.sleep(0.05)  # Ensure distinct filesystem mtime
        updated_data = [
            {"id": "doc1", "title": "Doc One", "keywords": ["doc1"], "summary": "s1", "content": "c1"},
            {"id": "doc2", "title": "Doc Two", "keywords": ["doc2"], "summary": "s2", "content": "c2"},
        ]
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(updated_data, f)

        # Calling retrieve() should detect mtime change and reload
        results = retriever.retrieve("doc2", top_k=1)
        assert len(retriever.documents) == 2
        assert len(results) == 1
        assert results[0]["id"] == "doc2"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_min_score_threshold():
    retriever = KnowledgeRetriever()
    # A single common word with no keyword/title matches should fall below min_score
    results = retriever.retrieve("the", top_k=5, min_score=100.0)
    assert len(results) == 0

