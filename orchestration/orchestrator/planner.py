import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

@registry.register("planner", AgentCapabilities(description="Plans and breaks down complex tasks.", tools=["plan"], agent_level="MANAGER"))
def planner_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Planner Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("PLANNER")
    # System instruction tailored for this agent
    sys_prompt = """You are the Planner Manager in an Agentic AI system.
Your job is to read the user's complex task and break it down into a step-by-step Execution Plan.
Each step must be assigned to one of the following specialized worker agents:
'coder', 'writer', 'designer', 'qa_tester', 'data_analyst', 'devops', 'security_auditor', 'seo_specialist', 'researcher', 'reasoner'.
You MUST output ONLY a valid JSON array of objects with the following schema:
[
  {
    "agent": "coder",
    "task": "detailed instruction for the coder"
  },
  {
    "agent": "devops",
    "task": "detailed instruction for devops"
  }
]"""
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="planner"
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="planner",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
