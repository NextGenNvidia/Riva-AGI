import pytest
from orchestration.orchestrator.main import reviewer_node, AgentState
from orchestration.orchestrator.schemas.task_spec import TaskStatus as SpecTaskStatus
from orchestration import InputData, InputType, AgentResponse, ResponseStatus

def test_reviewer_rejection_and_retry_cap(monkeypatch):
    # Mock reviewer agent to always reject
    from orchestration.orchestrator.registry import registry
    
    def mock_reviewer_reject(task_data):
        return AgentResponse(
            agent_id="reviewer",
            status=ResponseStatus.SUCCESS,
            content='{"status": "rejected", "feedback": "Code is missing error handling"}'
        )

    monkeypatch.setattr(registry, "get_agent", lambda name: mock_reviewer_reject if name == "reviewer" else None)

    plan = [
        {"task_id": "t1", "agent": "coder", "subtask": "Implement feature", "depends_on": [], "status": SpecTaskStatus.COMPLETED.value}
    ]

    state = {
        "task_payload": InputData(input_type=InputType.TEXT, text_content="Implement feature"),
        "agent": "coder",
        "response_payload": None,
        "task_id": "test-task-1",
        "session_id": "session-1",
        "source": "unit_test",
        "complexity": "complex",
        "routing_decision": "reviewer",
        "plan": plan,
        "current_step": 0,
        "current_task_id": "t1",
        "completed_steps": [{"agent": "coder", "result": "code with bug"}],
        "feedback": "",
        "retry_count": 0,
        "max_retries": 3,
        "intent": "coding",
        "confidence": 0.9,
    }

    # Attempt 1: rejection should set routing_decision="rejected", retry_count=1, and update plan feedback
    res1 = reviewer_node(state)
    assert res1["routing_decision"] == "rejected"
    assert res1["retry_count"] == 1
    assert res1["plan"][0]["status"] == SpecTaskStatus.PENDING.value
    assert "missing error handling" in res1["plan"][0]["feedback"]

    # Attempt 2: retry_count=2
    state["retry_count"] = 1
    res2 = reviewer_node(state)
    assert res2["routing_decision"] == "rejected"
    assert res2["retry_count"] == 2

    # Attempt 3: retry_count=3 reaches max_retries, escalates to fallback
    state["retry_count"] = 2
    res3 = reviewer_node(state)
    assert res3["routing_decision"] == "fallback"
    assert res3["retry_count"] == 3
