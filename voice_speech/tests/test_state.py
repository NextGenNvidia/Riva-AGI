"""Unit tests for ConversationState."""

import pytest
from voice_speech.engine.conversation.state import ConversationState


def test_conversation_state_lifecycle():
    state = ConversationState()
    assert state.session_active is True
    assert state.current_epoch == 0
    assert state.resumption_handle is None

    # Advance epoch
    ep1 = state.advance_epoch()
    assert ep1 == 1
    assert state.current_epoch == 1

    ep2 = state.advance_epoch()
    assert ep2 == 2

    # Terminate
    state.terminate()
    assert state.session_active is False
