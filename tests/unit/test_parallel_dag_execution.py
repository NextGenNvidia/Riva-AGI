"""
Unit Tests for Parallel DAG Wave Slicing & Concurrent Async Worker Pool (Pillars 1 & 6)
"""

import pytest
import time
from orchestration.orchestrator.schemas.task_spec import TaskSpec, TaskStatus
from orchestration.orchestrator.dag_scheduler import DAGScheduler
from orchestration.orchestrator.whiteboard import WhiteboardContext
from orchestration.orchestrator.executor import AsyncWorkerPool
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus


# Register mock agents for testing concurrent execution
@registry.register("mock_agent_a", AgentCapabilities(description="Mock agent A", tools=[]))
def mock_agent_a(data: InputData) -> AgentResponse:
    time.sleep(0.05)  # simulate brief work
    return AgentResponse(
        agent_id="mock_agent_a",
        status=ResponseStatus.SUCCESS,
        content="Output from Agent A"
    )

@registry.register("mock_agent_b", AgentCapabilities(description="Mock agent B", tools=[]))
def mock_agent_b(data: InputData) -> AgentResponse:
    time.sleep(0.05)  # simulate brief work
    return AgentResponse(
        agent_id="mock_agent_b",
        status=ResponseStatus.SUCCESS,
        content="Output from Agent B"
    )


def test_compute_execution_waves_diamond_dag():
    """
    Diamond DAG:
        task_01 (Root)
        ├── task_02 (Branch A)
        └── task_03 (Branch B)
        task_04 (Join: depends on task_02, task_03)
    """
    tasks = [
        TaskSpec(task_id="t1", agent="mock_agent_a", subtask="Root init", depends_on=[]),
        TaskSpec(task_id="t2", agent="mock_agent_a", subtask="Branch A", depends_on=["t1"]),
        TaskSpec(task_id="t3", agent="mock_agent_b", subtask="Branch B", depends_on=["t1"]),
        TaskSpec(task_id="t4", agent="mock_agent_a", subtask="Join result", depends_on=["t2", "t3"]),
    ]

    waves = DAGScheduler.compute_execution_waves(tasks)
    assert len(waves) == 3

    # Wave 0: Root task
    assert [t.task_id for t in waves[0]] == ["t1"]

    # Wave 1: Both branch tasks run concurrently
    wave_1_ids = set(t.task_id for t in waves[1])
    assert wave_1_ids == {"t2", "t3"}

    # Wave 2: Final join task
    assert [t.task_id for t in waves[2]] == ["t4"]


def test_compute_execution_waves_cycle_rejection():
    """Validates that cyclic DAGs raise ValueError in wave computation."""
    cyclic_tasks = [
        TaskSpec(task_id="t1", agent="mock_agent_a", subtask="Task 1", depends_on=["t2"]),
        TaskSpec(task_id="t2", agent="mock_agent_b", subtask="Task 2", depends_on=["t1"]),
    ]

    with pytest.raises(ValueError, match="Cycle detected"):
        DAGScheduler.compute_execution_waves(cyclic_tasks)


def test_async_worker_pool_concurrent_execution():
    """Verifies that AsyncWorkerPool executes a wave in parallel and updates whiteboard."""
    pool = AsyncWorkerPool(max_concurrency=4)
    wb = WhiteboardContext()

    wave = [
        TaskSpec(task_id="t_wave_1", agent="mock_agent_a", subtask="Do work A", depends_on=[]),
        TaskSpec(task_id="t_wave_2", agent="mock_agent_b", subtask="Do work B", depends_on=[]),
    ]

    start = time.time()
    responses = pool.run_wave_concurrently(wave, source="test", whiteboard=wb)
    elapsed = time.time() - start

    assert len(responses) == 2
    assert responses[0].status == ResponseStatus.SUCCESS
    assert responses[1].status == ResponseStatus.SUCCESS
    
    # Since each task took 0.05s, running 2 in parallel should take ~0.05-0.08s (not 0.10s+ sequential)
    assert elapsed < 0.09

    # Verify artifacts published to Whiteboard
    assert wb.get("t_wave_1_mock_agent_a_output") == "Output from Agent A"
    assert wb.get("t_wave_2_mock_agent_b_output") == "Output from Agent B"

    pool.shutdown()
