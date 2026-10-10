"""Integration tests for Riva-AGI Backend API Endpoints."""

import pytest
from starlette.testclient import TestClient

from Backend.main import app
from orchestration.orchestrator.state_manager import task_manager, TaskStatus


@pytest.fixture(scope="module")
def client():
    """Shared FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


# ─── Static Web UI Endpoints ──────────────────────────────────────────────────

def test_web_ui_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "").lower() or response.json()


def test_web_ui_app_js(client):
    response = client.get("/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()


def test_web_ui_worklet_js(client):
    response = client.get("/worklet.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()


def test_web_ui_favicon(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert "svg" in response.headers.get("content-type", "").lower()


# ─── API Metadata & System Endpoints ──────────────────────────────────────────

def test_api_info_endpoint(client):
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "endpoints" in data
    assert "voice_gateway" in data["endpoints"]
    assert "chat_rest" in data["endpoints"]


def test_system_health_endpoint(client):
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "services" in data
    assert "orchestrator" in data["services"]
    assert "voice" in data["services"]
    assert "rag" in data["services"]


def test_system_metrics_endpoint(client):
    response = client.get("/api/system/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "cpu" in data
    assert "memory" in data
    assert "battery" in data
    assert "gpu" in data
    assert "percent" in data["memory"]


def test_voice_status_endpoint(client):
    response = client.get("/api/voice/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "active_sessions" in data
    assert "max_concurrent_sessions" in data
    assert "circuit_breaker_open" in data


# ─── Agent Registry & Task State Endpoints ────────────────────────────────────

def test_agents_list_endpoint(client):
    response = client.get("/api/agents/list")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert len(data["agents"]) > 0

    agent_names = [a["name"] for a in data["agents"]]
    assert "coder" in agent_names
    assert "researcher" in agent_names


def test_tasks_status_not_found(client):
    response = client.get("/api/tasks/non-existent-task-id-1234")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_tasks_status_existing(client):
    # Register a task directly in task_manager
    test_id = "test-task-integration-999"
    task_manager.start_task(test_id, {"query": "Write a fast sort"})
    task_manager.update_task_state(test_id, "coder", TaskStatus.IN_PROGRESS)

    response = client.get(f"/api/tasks/{test_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == test_id
    assert data["status"] == "in_progress"
    assert data["owner"] == "coder"


# ─── RAG Query Endpoint ───────────────────────────────────────────────────────

def test_rag_query_endpoint(client):
    response = client.post("/api/rag/query", json={"query": "test query", "top_k": 2})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)


# ─── Voice WebSocket Endpoint Validation ──────────────────────────────────────

def test_voice_websocket_unauthorized_origin(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws", headers={"origin": "http://evil-attacker.com"}):
            pass


# ─── Chat REST Endpoint ───────────────────────────────────────────────────────

def test_chat_endpoint_rest(client, monkeypatch):
    async def mock_execute(task_text, session_id, source):
        return {
            "task_id": "test-task-123",
            "agent_used": "coder",
            "intent": "code_generation",
            "content": "def hello(): return 'world'",
            "status": "success",
            "execution_time_ms": 12.5,
            "tool_calls": [],
            "session_id": session_id,
        }

    from Backend.services.orchestrator_service import orchestrator_service
    monkeypatch.setattr(orchestrator_service, "execute_task", mock_execute)

    response = client.post(
        "/api/chat",
        json={"message": "Write a python script", "use_rag": False, "session_id": "test-sess-chat"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-123"
    assert data["agent_used"] == "coder"
    assert "def hello" in data["content"]
    assert data["session_id"] == "test-sess-chat"
