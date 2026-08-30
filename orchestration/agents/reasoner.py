import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

@registry.register("reasoner", AgentCapabilities(description="Provides logical reasoning.", tools=["reason"], agent_level="TASK_DOER"))
def reasoner_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Reasoner Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("REASONER")
    # System instruction tailored for this agent
    sys_prompt = f"You are the reasoner agent. Your job is to fulfill the user's request expertly."
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="reasoner"
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="reasoner",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
