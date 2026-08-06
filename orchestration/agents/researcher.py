import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus

logger = logging.getLogger(__name__)


@registry.register("researcher", AgentCapabilities(description="Handles internet research and data gathering.", tools=["search_web"]))
def researcher_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Researcher Agent")
    
    # Simulate execution time
    start_time = time.time()
    
    content = f"Researcher Agent investigated: {task_data.text_content}"
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="researcher",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )