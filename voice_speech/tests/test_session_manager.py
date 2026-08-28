"""Unit tests for SessionManager & Rate Limiting Circuit Breaker."""

import asyncio
import time
import pytest
from voice_speech.engine.conversation.session_manager import SessionManager


@pytest.mark.anyio
async def test_session_manager_concurrency_cap():
    mgr = SessionManager(max_concurrent_sessions=2, cooldown_seconds=10.0)

    # Acquire 1st session
    s1, err1 = await mgr.try_acquire()
    assert s1 is True
    assert err1 is None
    assert mgr.active_sessions == 1

    # Acquire 2nd session
    s2, err2 = await mgr.try_acquire()
    assert s2 is True
    assert err2 is None
    assert mgr.active_sessions == 2

    # Attempt 3rd session (should reject)
    s3, err3 = await mgr.try_acquire()
    assert s3 is False
    assert "capacity" in err3.lower()
    assert mgr.active_sessions == 2

    # Release one session
    await mgr.release()
    assert mgr.active_sessions == 1

    # Acquire again (should succeed)
    s4, err4 = await mgr.try_acquire()
    assert s4 is True
    assert err4 is None
    assert mgr.active_sessions == 2


@pytest.mark.anyio
async def test_session_manager_circuit_breaker():
    mgr = SessionManager(max_concurrent_sessions=5, cooldown_seconds=2.0)

    # Circuit breaker starts closed
    is_open, remaining = mgr.is_circuit_open()
    assert is_open is False
    assert remaining == 0

    # Trip the circuit breaker
    mgr.trip_circuit_breaker()
    is_open, remaining = mgr.is_circuit_open()
    assert is_open is True
    assert remaining > 0

    # try_acquire should be rejected immediately with cooldown message
    acquired, err = await mgr.try_acquire()
    assert acquired is False
    assert "cooldown active" in err.lower()

    # Wait for cooldown to expire
    await asyncio.sleep(2.1)
    is_open_after, remaining_after = mgr.is_circuit_open()
    assert is_open_after is False
    assert remaining_after == 0

    # Now acquire should succeed
    acquired_after, err_after = await mgr.try_acquire()
    assert acquired_after is True
    assert err_after is None
