"""
Executor Agent — orchestration/orchestrator/executor.py
========================================================
Pure deterministic DAG executor resolving next ready task in <1ms without LLM latency.
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus, InputType
from orchestration.orchestrator.schemas.task_spec import TaskSpec, TaskStatus
from orchestration.orchestrator.dag_scheduler import DAGScheduler

logger = logging.getLogger(__name__)

@registry.register("executor", AgentCapabilities(description="Executes cross-agent tasks using 0ms DAG scheduling.", tools=["execute"], agent_level="MANAGER"))
def executor_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Deterministic DAG Executor Agent")
    start_time = time.time()
    
    text = task_data.text_content or ""
    # Parse plan if provided in json
    tasks = []
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "tasks" in data:
            tasks_data = data["tasks"]
        elif isinstance(data, list):
            tasks_data = data
        else:
            tasks_data = []

        for item in tasks_data:
            if isinstance(item, dict):
                tasks.append(
                    TaskSpec(
                        task_id=item.get("task_id", f"task_{len(tasks)+1}"),
                        agent=item.get("agent", "coder"),
                        subtask=item.get("subtask") or item.get("task", ""),
                        depends_on=item.get("depends_on", []),
                        status=TaskStatus(item.get("status", "pending"))
                    )
                )
    except Exception as e:
        logger.debug(f"Executor received non-json payload: {e}")

    if tasks:
        next_task = DAGScheduler.get_next_task(tasks)
        if next_task:
            res_content = json.dumps({"action": "delegate", "target": next_task.agent, "task_id": next_task.task_id})
        else:
            res_content = json.dumps({"action": "review", "target": "reviewer"})
    else:
        res_content = json.dumps({"action": "review", "target": "reviewer"})

    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="executor",
        status=ResponseStatus.SUCCESS,
        content=res_content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )


class AsyncWorkerPool:
    """
    Concurrent Async Worker Pool (Pillars 1 & 6).
    Dispatches multiple DAG subtasks simultaneously across thread/async pools.
    """

    def __init__(self, max_concurrency: int = 5):
        from concurrent.futures import ThreadPoolExecutor
        self.max_concurrency = max_concurrency
        self._thread_pool = ThreadPoolExecutor(max_workers=max_concurrency)

    def execute_single_task(
        self,
        task: TaskSpec,
        source: str = "cli",
        whiteboard: Optional[Any] = None
    ) -> AgentResponse:
        """Executes a single subtask with upstream whiteboard artifact injection."""
        handler = registry.get_agent(task.agent)
        if not handler:
            return AgentResponse(
                agent_id=task.agent,
                status=ResponseStatus.FAILURE,
                content=f"Agent '{task.agent}' not found in registry.",
                tool_calls=[],
                error_message=f"Agent '{task.agent}' missing."
            )

        prompt = task.subtask
        if whiteboard and task.depends_on:
            upstream = whiteboard.format_context_for_prompt(task.depends_on)
            if upstream:
                prompt += f"\n\n[UPSTREAM ARTIFACTS FROM WHITEBOARD]:\n{upstream}"

        input_data = InputData(
            input_type=InputType.TEXT,
            text_content=prompt,
            metadata={"task_id": task.task_id, "source": source}
        )

        response = handler(input_data)

        # Publish result to whiteboard
        if whiteboard:
            art_type = "code" if task.agent in ("coder", "devops") else ("json_schema" if task.agent == "designer" else "text")
            whiteboard.publish(
                key=f"{task.task_id}_{task.agent}_output",
                content=response.content,
                author=task.agent,
                task_id=task.task_id,
                artifact_type=art_type
            )

        task.status = TaskStatus.COMPLETED
        task.result = response.content
        return response

    def run_wave_concurrently(
        self,
        wave: List[TaskSpec],
        source: str = "cli",
        whiteboard: Optional[Any] = None
    ) -> List[AgentResponse]:
        """
        Executes an entire wave of independent tasks simultaneously.
        Blocks until all tasks in the wave complete.
        """
        if not wave:
            return []

        futures = [
            self._thread_pool.submit(self.execute_single_task, task, source, whiteboard)
            for task in wave
        ]
        return [f.result() for f in futures]

    async def execute_wave_async(
        self,
        wave: List[TaskSpec],
        source: str = "cli",
        whiteboard: Optional[Any] = None
    ) -> List[AgentResponse]:
        """Asyncio coroutine to execute a wave concurrently using asyncio.gather."""
        import asyncio
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(self._thread_pool, self.execute_single_task, task, source, whiteboard)
            for task in wave
        ]
        return await asyncio.gather(*tasks)

    def shutdown(self):
        """Cleanly terminates the worker thread pool."""
        self._thread_pool.shutdown(wait=False)

