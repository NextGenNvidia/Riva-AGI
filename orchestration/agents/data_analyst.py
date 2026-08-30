import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

@registry.register("data_analyst", AgentCapabilities(description="Analyzes data and numbers.", tools=["analyze"], agent_level="TASK_DOER"))
def data_analyst_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Data Analyst Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("WORKER_7")
    # System instruction tailored for this agent
    sys_prompt = f"You are the data_analyst agent. Your job is to fulfill the user's request expertly."
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="data_analyst"
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="data_analyst",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
