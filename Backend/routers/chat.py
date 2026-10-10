"""Chat Router supporting synchronous REST and real-time streaming WebSocket."""

import asyncio
import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from Backend.models.chat import ChatRequest, ChatResponse
from Backend.services.orchestrator_service import orchestrator_service
from Backend.services.rag_service import rag_service
from Backend.session.store import session_store

logger = logging.getLogger("riva.backend.routers.chat")

router = APIRouter(tags=["Chat & Multi-Agent Orchestration"])


@router.post("", response_model=ChatResponse, summary="Synchronous Chat Request")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Executes a user prompt through Riva-AGI's multi-agent orchestrator.

    Optionally enriches the task with relevant knowledge from RAG before invoking
    the LangGraph hierarchy (Intent -> Planner -> Executor -> Workers -> Reviewer).
    """
    session_id = request.session_id or f"sess-{uuid.uuid4().hex[:8]}"

    # 1. Optionally enrich with RAG knowledge
    task_text = request.message
    if request.use_rag:
        task_text = await rag_service.enrich_task_with_rag(request.message)

    # 2. Run orchestrator asynchronously
    res_data = await orchestrator_service.execute_task(
        task_text=task_text,
        session_id=session_id,
        source="api_chat",
    )

    # 3. Save to multi-turn session store
    session_store.add_turn(session_id, request.message, res_data)

    return ChatResponse(**res_data)


@router.websocket("/stream")
async def chat_stream_endpoint(websocket: WebSocket) -> None:
    """Real-time WebSocket streaming endpoint for word-by-word agent outputs."""
    await websocket.accept()
    logger.info("Client connected to /api/chat/stream")

    try:
        while True:
            data = await websocket.receive_json()
            message = str(data.get("message", "")).strip()
            session_id = str(data.get("session_id") or f"stream-{uuid.uuid4().hex[:8]}")
            use_rag = bool(data.get("use_rag", True))

            if not message:
                await websocket.send_json({"type": "error", "message": "No message provided."})
                continue

            # Notify stream started
            await websocket.send_json({
                "type": "start",
                "session_id": session_id,
                "message": message,
            })

            # Pre-fetch RAG
            task_text = message
            if use_rag:
                await websocket.send_json({"type": "status", "data": "Searching knowledge base..."})
                task_text = await rag_service.enrich_task_with_rag(message)

            await websocket.send_json({"type": "status", "data": "Orchestrating agents..."})

            # Run orchestrator
            res_data = await orchestrator_service.execute_task(
                task_text=task_text,
                session_id=session_id,
                source="api_stream",
            )
            content = res_data.get("content", "")

            # Stream words
            words = content.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                await websocket.send_json({"type": "token", "data": chunk})
                await asyncio.sleep(0.01)

            # Send done event with final structured metadata
            await websocket.send_json({"type": "done", "data": res_data})

            # Persist turn
            session_store.add_turn(session_id, message, res_data)

    except WebSocketDisconnect:
        logger.info("Client disconnected cleanly from /api/chat/stream")
    except Exception as e:
        logger.error("Error in chat streaming WebSocket: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
