from orchestration.orchestrator.schemas.response import ResponseStatus
from orchestration.orchestrator.main import run_orchestrator


def test_coding_task_orchestration():
    result = run_orchestrator(
        "Draft a Python function for sorting"
    )

    assert result["agent"] == "coder"
    assert result["intent"] == "coding"
    assert result["response_payload"].status == ResponseStatus.SUCCESS
    assert result["response_payload"].content is not None


def test_unknown_task_uses_fallback():
    result = run_orchestrator("hello xyz random task")

    assert result["agent"] == "fallback"
    assert result["intent"] == "unknown"
    assert result["confidence"] == 0.0
    assert "couldn't confidently determine" in result["response_payload"].content