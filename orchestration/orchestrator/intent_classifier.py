import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

@registry.register("intent_classifier", AgentCapabilities(description="Classifies the user's intent.", tools=["classify"], agent_level="MANAGER"))
def intent_classifier_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Intent Classifier Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("INTENT")
    # System instruction tailored for this agent
    sys_prompt = """You are the Intent Classifier Manager in an Agentic AI system.
Your job is to read the user's task and output a JSON block describing the intent.
Determine if the task is simple (can be done by one specialized worker agent) or complex (requires multi-step planning).
If simple, specify the 'target_agent' (e.g., 'coder', 'devops', 'writer', 'seo_specialist', 'qa_tester', 'designer', etc.).
If complex, set 'target_agent' to 'planner'.
You MUST output ONLY a valid JSON object with the following schema:
{
  "complexity": "simple" | "complex",
  "target_agent": "agent_name",
  "intent": "short description of intent",
  "confidence": 0.9
}"""
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="intent_classifier"
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="intent_classifier",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
