"""
Unit Tests for Hierarchical Domain Decomposition & RAG Knowledge Hook (Pillars 2 & 5)
"""

import pytest
from orchestration.orchestrator.planner import (
    detect_workstreams,
    plan_hierarchical_tasks,
)
from orchestration.orchestrator.dag_scheduler import DAGScheduler
from orchestration.orchestrator.schemas.task_spec import TaskSpec
from orchestration.orchestrator.registry import registry
from orchestration import InputData, ResponseStatus, InputType
import orchestration.agents.knowledge_agent


def test_detect_workstreams_multi_domain():
    goal = "Build a FastAPI backend with authentication, run pytest, and write documentation"
    domains = detect_workstreams(goal)
    assert "engineering" in domains
    assert "verification" in domains
    assert "content_docs" in domains


def test_plan_hierarchical_tasks_generates_valid_parallel_dag():
    goal = "Build FastAPI backend, test with pytest, and write README documentation"
    tasks_dict = plan_hierarchical_tasks(goal)

    assert len(tasks_dict) >= 3
    agents = [t["agent"] for t in tasks_dict]
    assert "coder" in agents
    assert "qa_tester" in agents
    assert "writer" in agents

    # Convert to TaskSpec and verify DAG validity
    task_specs = [
        TaskSpec(
            task_id=t["task_id"],
            agent=t["agent"],
            subtask=t["subtask"],
            depends_on=t["depends_on"]
        )
        for t in tasks_dict
    ]

    # No cycles
    assert not DAGScheduler.detect_cycle(task_specs)

    # Compute execution waves
    waves = DAGScheduler.compute_execution_waves(task_specs)
    assert len(waves) >= 2

    # Wave 0 is coder
    assert waves[0][0].agent == "coder"

    # Wave 1 has qa_tester and writer running in parallel!
    wave_1_agents = {t.agent for t in waves[1]}
    assert "qa_tester" in wave_1_agents
    assert "writer" in wave_1_agents


def test_knowledge_agent_registered_and_callable():
    handler = registry.get_agent("knowledge_agent")
    assert handler is not None

    input_data = InputData(input_type=InputType.TEXT, text_content="What is the system architecture policy?")
    response = handler(input_data)

    assert response.status == ResponseStatus.SUCCESS
    assert response.agent_id == "knowledge_agent"
    assert "architecture_guide.md" in response.content
    assert response.metadata["chunks_retrieved"] > 0


def test_plan_browser_automation_workstream():
    goal = "Ye leetcode problem solve karo aur browser me code type karo"
    domains = detect_workstreams(goal)
    assert "browser_automation" in domains

    tasks = plan_hierarchical_tasks(goal)
    assert len(tasks) == 3
    assert tasks[0]["agent"] == "researcher"
    assert tasks[1]["agent"] == "coder"
    assert tasks[2]["agent"] == "qa_tester"
    assert tasks[1]["depends_on"] == [tasks[0]["task_id"]]
    assert tasks[2]["depends_on"] == [tasks[1]["task_id"]]

