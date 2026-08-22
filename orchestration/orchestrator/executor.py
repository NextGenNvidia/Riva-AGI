import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

@registry.register("executor", AgentCapabilities(description="Executes cross-agent tasks.", tools=["execute"], agent_level="MANAGER"))
def executor_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Executor Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("EXECUTOR")
    # System instruction tailored for this agent
    sys_prompt = """You are the Executor Manager in an Agentic AI system.
You will be provided with an Execution Plan (JSON array) and the current execution state (what step we are on, what has been completed).
Your job is to determine the NEXT action to take.
If there are remaining steps in the plan, your action is 'delegate' and the target is the agent assigned to the next step.
If all steps are completed, your action is 'review' and the target is 'reviewer'.
You MUST output ONLY a valid JSON object with the following schema:
{
  "action": "delegate" | "review",
  "target": "agent_name" | "reviewer"
}"""
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="executor"
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="executor",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
