import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

@registry.register("qa_tester", AgentCapabilities(description="Runs quality assurance tests.", tools=["test"], agent_level="TASK_DOER"))
def qa_tester_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to QA Tester Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("WORKER_6")
    # System instruction tailored for this agent
    sys_prompt = f"You are the qa_tester agent. Your job is to fulfill the user's request expertly."
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="qa_tester"
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="qa_tester",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
