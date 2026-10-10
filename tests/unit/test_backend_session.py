"""Unit tests for Backend SessionStore."""

import pytest
from Backend.session.store import SessionStore


def test_session_store_create_and_retrieve():
    store = SessionStore()
    sess = store.get_or_create("test-sess-1")
    assert sess["session_id"] == "test-sess-1"
    assert sess["history"] == []
    assert "created_at" in sess


def test_session_store_add_turn():
    store = SessionStore()
    sess_id = "test-sess-2"
    store.add_turn(
        session_id=sess_id,
        user_message="Hello, Riva!",
        agent_response={
            "content": "Hello! How can I help you?",
            "agent_used": "coder",
            "task_id": "task-abc",
            "status": "success",
        },
    )

    history = store.get_history(sess_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello, Riva!"
    assert history[1]["role"] == "assistant"
    assert history[1]["agent"] == "coder"
    assert history[1]["status"] == "success"


def test_session_store_nonexistent_history():
    store = SessionStore()
    assert store.get_history("nonexistent") == []


def test_session_store_clear():
    store = SessionStore()
    store.get_or_create("s1")
    store.get_or_create("s2")
    assert len(store.get_all_sessions()) == 2
    store.clear()
    assert len(store.get_all_sessions()) == 0
