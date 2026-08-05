from orchestration.orchestrator.router import classify_intent


def test_coding_task():
    result = classify_intent("Draft a Python function for sorting")

    assert result["intent"] == "coding"
    assert result["agent"] == "coder"
    assert result["confidence"] > 0


def test_research_task():
    result = classify_intent("Why is machine learning important?")

    assert result["intent"] == "research"
    assert result["agent"] == "researcher"
    assert result["confidence"] > 0


def test_unknown_task():
    result = classify_intent("hello xyz random task")

    assert result["intent"] == "unknown"
    assert result["agent"] == "fallback"
    assert result["confidence"] == 0.0


def test_empty_task():
    result = classify_intent("   ")

    assert result["intent"] == "unknown"
    assert result["agent"] == "fallback"
    assert result["confidence"] == 0.0