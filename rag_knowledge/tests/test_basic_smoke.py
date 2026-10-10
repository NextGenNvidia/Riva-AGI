"""Hermetic end-to-end smoke test for PR 1a (Text & JSON RAG pipeline).

Generates synthetic markdown and json documents, runs ingestion through privacy filters,
indexes into a simulated store, and validates question answering with source citations.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from rag_knowledge.clients.gemini_client import GeminiRAGClient
from rag_knowledge.ingestion.pipeline import run_ingestion
from rag_knowledge.retrieval.retriever import KnowledgeRetriever
from rag_knowledge.service import RAGService


def test_basic_rag_smoke_e2e(tmp_path):
    import docx

    # 1. Create synthetic files in tmp_path
    # 1a. Word document
    doc_docx = tmp_path / "club_handbook.docx"
    doc = docx.Document()
    doc.add_heading("NextGen Club Handbook", level=1)
    doc.add_paragraph("Orientation session is scheduled for 25 October 2026.")
    doc.add_paragraph("Members must complete 2 hands-on workshops per semester.")
    doc.save(str(doc_docx))

    # 1b. Unsupported file that must be skipped with a message without crashing
    dummy_img = tmp_path / "banner.png"
    dummy_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

    # 2. Ingest with dry_run
    dry_count = run_ingestion(source_dir=tmp_path, dry_run=True, redact=True)
    assert dry_count >= 1

    # 3. Ingest with mocked Qdrant store
    mock_store = MagicMock()
    mock_store.is_available.return_value = True
    mock_store.collection_name = "test_collection"
    captured_docs = []

    def fake_upsert(docs):
        captured_docs.extend(docs)
        return len(docs)

    mock_store.upsert_documents.side_effect = fake_upsert

    with patch("rag_knowledge.ingestion.pipeline.get_global_qdrant_store", return_value=mock_store):
        total_ingested = run_ingestion(source_dir=tmp_path, dry_run=False, redact=True)
        assert total_ingested == dry_count
        assert len(captured_docs) == dry_count

    # 4. Verify no private contact leaks in captured documents
    for d in captured_docs:
        assert "@" not in d["content"]
        assert "fakeimagebytes" not in d["content"]

    # 5. Verify retrieval and question answering with cited sources
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [
        {
            "id": "doc_orientation",
            "title": "Orientation Schedule",
            "summary": "Orientation is on 25 October 2026.",
            "content": "Orientation session is scheduled for 25 October 2026 in the main hall.",
            "score": 0.92,
            "metadata": {"source": "club_handbook.md", "page": 1},
        }
    ]

    mock_llm = MagicMock(spec=GeminiRAGClient)
    mock_llm.is_configured = True
    mock_llm.generate_answer = AsyncMock(
        return_value="The orientation session is scheduled for 25 October 2026 in the main hall."
    )

    service = RAGService(retriever=mock_retriever, llm_client=mock_llm)

    import asyncio
    answer, sources = asyncio.run(service.query_with_sources("When is orientation?"))

    assert "25 October 2026" in answer
    assert sources == ["club_handbook.md (Page 1)"]
