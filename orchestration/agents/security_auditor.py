import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

@registry.register("security_auditor", AgentCapabilities(description="Audits code for vulnerabilities.", tools=["audit"], agent_level="TASK_DOER"))
def security_auditor_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Security Auditor Agent")
    start_time = time.time()
    
    my_key = key_manager.get_api_key_for_role("SECURITY_AUDITOR")
    # System instruction tailored for this agent
    sys_prompt = "You are the Senior Application Security Auditor Agent. Your mission is to audit source code, identify vulnerabilities (OWASP Top 10, CWE), assess attack surfaces, and recommend robust remediations."
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="security_auditor"
    )
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="security_auditor",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
