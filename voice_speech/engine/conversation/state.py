"""Conversation State Management for active WebSocket sessions.

Encapsulates per-client audio state, barge-in epoch tracking, session resumption handle,
and thread-safe WebSocket transmission helpers.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from fastapi import WebSocket


@dataclass
class ConversationState:
    """Encapsulates all mutable state for an individual active conversation session."""
    session_active: bool = True
    current_epoch: int = 0
    resumption_handle: Optional[str] = None
    mic_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=30))
    ws_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def advance_epoch(self) -> int:
        """Increments the epoch counter on barge-in to invalidate obsolete playback buffers."""
        self.current_epoch += 1
        return self.current_epoch

    def terminate(self) -> None:
        """Marks the session as inactive."""
        self.session_active = False

    async def safe_send_json(self, websocket: WebSocket, data: dict) -> None:
        """Thread-safe WebSocket JSON message delivery."""
        if not self.session_active:
            return
        async with self.ws_lock:
            try:
                await websocket.send_json(data)
            except Exception:
                pass

    async def safe_send_bytes(self, websocket: WebSocket, data: bytes) -> None:
        """Thread-safe WebSocket binary payload delivery."""
        if not self.session_active:
            return
        async with self.ws_lock:
            try:
                await websocket.send_bytes(data)
            except Exception:
                pass
