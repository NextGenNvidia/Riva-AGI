"""Session Manager & Rate Limiting Circuit Breaker.

Manages concurrency limits and quota exhaustion circuit-breaking across all WebSocket sessions.
"""

import asyncio
import logging
import os
import time
from typing import Optional, Tuple

logger = logging.getLogger("riva.session_manager")


class SessionManager:
    """Manages active connection concurrency and server-side rate limit circuit breaker."""

    def __init__(
        self,
        max_concurrent_sessions: Optional[int] = None,
        cooldown_seconds: Optional[float] = None,
    ):
        self.max_concurrent_sessions = (
            max_concurrent_sessions
            if max_concurrent_sessions is not None
            else int(os.getenv("MAX_CONCURRENT_SESSIONS", "5"))
        )
        self.cooldown_seconds = (
            cooldown_seconds
            if cooldown_seconds is not None
            else float(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SEC", "45.0"))
        )
        self._active_sessions = 0
        self._session_lock = asyncio.Lock()
        self._last_quota_exhausted_time = 0.0

    @property
    def active_sessions(self) -> int:
        return self._active_sessions

    def is_circuit_open(self) -> Tuple[bool, int]:
        """Checks if the circuit breaker is currently active due to recent quota exhaustion.

        Returns:
            Tuple of (is_open: bool, remaining_seconds: int).
        """
        elapsed = time.time() - self._last_quota_exhausted_time
        if elapsed < self.cooldown_seconds:
            remaining = int(self.cooldown_seconds - elapsed)
            return True, remaining
        return False, 0

    def trip_circuit_breaker(self) -> None:
        """Trips the circuit breaker on quota exhaustion (1011 / 429)."""
        self._last_quota_exhausted_time = time.time()
        logger.warning(
            f"Circuit breaker tripped! Rejecting new sessions for {self.cooldown_seconds}s."
        )

    async def try_acquire(self) -> Tuple[bool, Optional[str]]:
        """Attempts to acquire a session slot under concurrency and circuit-breaker constraints.

        Returns:
            Tuple of (success: bool, error_message: Optional[str]).
        """
        # 1. Check circuit breaker cooldown
        is_open, remaining = self.is_circuit_open()
        if is_open:
            logger.warning(f"Rejected connection: Rate limit cooldown active ({remaining}s remaining).")
            return False, f"Gemini API rate limit cooldown active. Please wait {remaining}s before retrying."

        # 2. Check concurrent capacity
        async with self._session_lock:
            if self._active_sessions >= self.max_concurrent_sessions:
                logger.warning(
                    f"Rejected connection: Server at capacity ({self._active_sessions}/{self.max_concurrent_sessions} sessions)."
                )
                return False, f"Server at capacity ({self.max_concurrent_sessions} sessions). Try again later."
            self._active_sessions += 1
            logger.info(f"Session acquired [{self._active_sessions}/{self.max_concurrent_sessions} active]")
            return True, None

    async def release(self) -> None:
        """Releases an active session slot."""
        async with self._session_lock:
            self._active_sessions = max(0, self._active_sessions - 1)
            logger.info(f"Session released [{self._active_sessions}/{self.max_concurrent_sessions} active]")
