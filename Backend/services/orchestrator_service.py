"""Orchestrator Execution Service for Riva-AGI.

Encapsulates invocation of the LangGraph multi-agent pipeline within an async-safe
worker thread and normalizes structured response outputs.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List

from orchestration.orchestrator.main import run_orchestrator
from orchestration.orchestrator.registry import registry
from orchestration.orchestrator.state_manager import task_manager

logger = logging.getLogger("riva.backend.orchestrator_service")


class OrchestratorService:
    """Coordinates execution and state tracking for multi-agent workflows."""

    @staticmethod
    def extract_response_data(result: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Normalizes raw LangGraph execution outputs into standard response schema."""
        task_id = result.get("task_id", f"task-{uuid.uuid4().hex[:8]}")
        agent_used = result.get("agent", "orchestrator")
        intent = result.get("intent", "unknown")
        response_payload = result.get("response_payload")

        content = ""
        status = "success"
        execution_time_ms = 0.0
        tool_calls: List[Dict[str, Any]] = []

        if response_payload:
            content = getattr(response_payload, "content", "") or ""
            st = getattr(response_payload, "status", None)
            status = st.value if hasattr(st, "value") else str(st or "success")
            execution_time_ms = getattr(response_payload, "execution_time_ms", 0.0) or 0.0
            raw_tools = getattr(response_payload, "tool_calls", []) or []
            for tc in raw_tools:
                if hasattr(tc, "model_dump"):
                    tool_calls.append(tc.model_dump())
                elif isinstance(tc, dict):
                    tool_calls.append(tc)

        return {
            "task_id": task_id,
            "agent_used": agent_used,
            "intent": intent,
            "content": content,
            "status": status,
            "execution_time_ms": execution_time_ms,
            "tool_calls": tool_calls,
            "session_id": session_id,
        }

    async def execute_task(
        self,
        task_text: str,
        session_id: str,
        source: str = "api",
    ) -> Dict[str, Any]:
        """Runs the LangGraph orchestrator synchronously inside an asyncio worker thread."""
        result = await asyncio.to_thread(
            run_orchestrator,
            task_text=task_text,
            session_id=session_id,
            source=source,
        )
        return self.extract_response_data(result, session_id)

    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any] | None:
        """Retrieves task execution state and step history from TaskStateManager."""
        state = task_manager.get_task_status(task_id)
        if state is None:
            return None
        return state.model_dump()

    @staticmethod
    def get_agent_capabilities() -> Dict[str, Any]:
        """Returns all registered agent capabilities."""
        return registry.get_all_capabilities()


# Global singleton instance
orchestrator_service = OrchestratorService()
