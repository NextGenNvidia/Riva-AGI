import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus

logger = logging.getLogger(__name__)


@registry.register("coder", AgentCapabilities(description="Handles coding and software development tasks.", tools=["write_code"]))
def coder_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Coder Agent")
    
    # Simulate execution time
    start_time = time.time()
    
    content = f"Coder Agent processed text: {task_data.text_content}"
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="coder",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )