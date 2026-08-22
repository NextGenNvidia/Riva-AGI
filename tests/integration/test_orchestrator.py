from orchestration.orchestrator.main import run_orchestrator


def test_coding_task_orchestration():
    result = run_orchestrator(
        "Draft a Python function for sorting"
    )

    assert result["agent"] == "coder"
    assert result["response_payload"].content is not None
    assert len(result["response_payload"].content) > 0


def test_unknown_task_uses_fallback():
    result = run_orchestrator("hello xyz random task")

    assert result["agent"] == "fallback"
    assert "Fallback agent reached" in result["response_payload"].content