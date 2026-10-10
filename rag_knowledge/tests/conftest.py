"""Pytest configuration and hermetic isolation fixtures for rag_knowledge."""

import os
import pytest
from unittest.mock import MagicMock
import rag_knowledge.storage.mongo as mongo_mod
import rag_knowledge.service as service_mod


@pytest.fixture
def anyio_backend():
    """Pins anyio to asyncio for all async test cases."""
    return "asyncio"


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    """Enforces hermetic test isolation by clearing real external credentials from environment."""
    # Prevent tests from discovering live MongoDB or Gemini credentials
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_RAG_MODEL", raising=False)
    monkeypatch.setenv("RAG_LOAD_CWD_ENV", "false")

    # Reset any cached global stores or services
    mongo_mod._GLOBAL_STORE = None
    service_mod._GLOBAL_SERVICE = None

    yield

    # Clean up afterwards
    mongo_mod._GLOBAL_STORE = None
    service_mod._GLOBAL_SERVICE = None
