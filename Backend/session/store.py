"""Thread-safe multi-turn session storage for Riva-AGI."""

import datetime
import threading
from typing import Any, Dict, List, Optional


class SessionStore:
    """Thread-safe in-memory multi-turn session store for Riva-AGI."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def get_or_create(self, session_id: str) -> Dict[str, Any]:
        """Retrieves an existing session or initializes a new one."""
        with self._lock:
            if session_id not in self._sessions:
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._sessions[session_id] = {
                    "session_id": session_id,
                    "history": [],
                    "created_at": now_str,
                    "updated_at": now_str,
                }
            return self._sessions[session_id]

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        agent_response: Dict[str, Any],
    ) -> None:
        """Records a completed dialog turn (user prompt + agent response) into session history."""
        with self._lock:
            session = self.get_or_create(session_id)
            now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

            session["history"].append({
                "role": "user",
                "content": user_message,
                "timestamp": now_str,
            })
            session["history"].append({
                "role": "assistant",
                "content": agent_response.get("content", ""),
                "agent": agent_response.get("agent_used", "orchestrator"),
                "task_id": agent_response.get("task_id", ""),
                "status": agent_response.get("status", "success"),
                "timestamp": now_str,
            })
            session["updated_at"] = now_str

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns the chronological turn history for a given session."""
        with self._lock:
            if session_id in self._sessions:
                return list(self._sessions[session_id]["history"])
            return []

    def get_all_sessions(self) -> List[str]:
        """Returns all active session IDs."""
        with self._lock:
            return list(self._sessions.keys())

    def clear(self) -> None:
        """Clears all stored sessions."""
        with self._lock:
            self._sessions.clear()


# Global singleton instance
session_store = SessionStore()
