"""Tests for MistralRAGClient in rag_knowledge."""

import json
from unittest.mock import MagicMock, patch
import pytest
from rag_knowledge.mistral_client import MistralRAGClient


def test_client_configuration():
    client_unconfigured = MistralRAGClient(api_key="")
    assert not client_unconfigured.is_configured

    client_configured = MistralRAGClient(api_key="mock-key-12345")
    assert client_configured.is_configured
    assert client_configured.api_key == "mock-key-12345"


@pytest.mark.anyio
async def test_generate_answer_unconfigured():
    client = MistralRAGClient(api_key="")
    # Should return None smoothly without raising exception
    result = await client.generate_answer("Who is Raj?", "Raj is a researcher.")
    assert result is None


@pytest.mark.anyio
async def test_generate_answer_mock_success():
    client = MistralRAGClient(api_key="mock-key-123")

    fake_response_data = {
        "choices": [
            {
                "message": {
                    "content": "Raj Ojha is a core lead and AI researcher at NextGen SuperComputing Club."
                }
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(fake_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        answer = await client.generate_answer(
            query="Who is Raj Ojha?",
            context="Raj Ojha is a core lead at NextGen club."
        )
        assert answer == "Raj Ojha is a core lead and AI researcher at NextGen SuperComputing Club."


@pytest.mark.anyio
async def test_generate_answer_api_error():
    client = MistralRAGClient(api_key="mock-key-123")

    with patch("urllib.request.urlopen", side_effect=Exception("Connection timeout")):
        # Should gracefully catch error and return None (triggering RAG fallback)
        answer = await client.generate_answer("query", "context")
        assert answer is None
