"""
Conversation State Machine for Riva.
"""

from enum import Enum, auto
import time
from typing import Callable, List, Optional
import asyncio
import logging

logger = logging.getLogger("riva.state")


class ConversationState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    LISTENING = auto()
    USER_SPEAKING = auto()
    MODEL_RESPONDING = auto()
    PLAYING_AUDIO = auto()
    BARGE_IN = auto()
    SESSION_RESUMING = auto()
    RECONNECTING = auto()
    ERROR = auto()


class StateManager:
    """Manages conversational state transitions and event callbacks."""

    def __init__(self, initial_state: ConversationState = ConversationState.DISCONNECTED):
        self._state: ConversationState = initial_state
        self._last_transition_time: float = time.monotonic()
        self._listeners: List[Callable[[ConversationState, ConversationState], None]] = []
        self._lock = asyncio.Lock()

    @property
    def current_state(self) -> ConversationState:
        return self._state

    def add_listener(self, callback: Callable[[ConversationState, ConversationState], None]) -> None:
        """Register a callback for state changes (old_state, new_state)."""
        self._listeners.append(callback)

    def transition_to(self, new_state: ConversationState) -> None:
        """Synchronously record transition and notify listeners."""
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state
        now = time.monotonic()
        delta_ms = (now - self._last_transition_time) * 1000.0
        self._last_transition_time = now

        logger.debug(f"State transition: {old_state.name} -> {new_state.name} (after {delta_ms:.1f}ms)")

        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state listener: {e}", exc_info=True)

    def is_active(self) -> bool:
        """Return true if connected and in an operational state."""
        return self._state not in (
            ConversationState.DISCONNECTED,
            ConversationState.ERROR,
            ConversationState.RECONNECTING,
        )
