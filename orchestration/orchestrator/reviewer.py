"""
Reviewer Agent — orchestration/orchestrator/reviewer.py
========================================================
Agent-Aware Quality Gate leveraging Laya non-autoregressive verification (<35ms)
across 10 Domain Profiles with fallback critique generation.
"""
import json
import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini
from orchestration.orchestrator.laya_engine import laya_engine

logger = logging.getLogger(__name__)

def clean_json_text(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

@registry.register("reviewer", AgentCapabilities(description="Reviews generated content and code using domain verification profiles.", tools=["review"], agent_level="MANAGER"))
def reviewer_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Reviewer Agent")
    start_time = time.time()
    
    text = task_data.text_content or ""
    metadata = task_data.metadata or {}
    target_agent = metadata.get("target_agent", "coder")
    goal = metadata.get("goal", text)

    # 1. Fast-Path Domain Verification with Laya Noul (<35ms)
    is_valid, score = laya_engine.verify_domain_output(output=text, agent_name=target_agent, goal=goal)
    logger.info(f"[Reviewer] Domain check for [{target_agent}]: valid={is_valid}, score={score:.2f}")

    if is_valid:
        res_data = {
            "status": "approved",
            "feedback": f"Output satisfies domain verification criteria for [{target_agent}] (confidence: {score:.2f})."
        }
        content = json.dumps(res_data, indent=2)
    else:
        # If domain verification failed, use LLM or generate targeted critique
        my_key = key_manager.get_api_key_for_role("REVIEWER")
        sys_prompt = f"""You are the Reviewer Manager for Riva-AGI.
Evaluate if the worker output for [{target_agent}] fulfills the goal: '{goal}'.
Output ONLY valid JSON:
{{
  "status": "approved" | "rejected",
  "feedback": "constructive feedback"
}}"""
        try:
            llm_res = call_gemini(
                prompt=f"Goal: {goal}\nOutput to review:\n{text}",
                api_key=my_key,
                system_instruction=sys_prompt,
                agent_id="reviewer"
            )
            parsed = json.loads(clean_json_text(llm_res))
            content = json.dumps(parsed, indent=2)
        except Exception as e:
            logger.warning(f"Reviewer LLM evaluation fallback: {e}")
            res_data = {
                "status": "rejected",
                "feedback": f"Output for [{target_agent}] requires revision to meet domain quality standards."
            }
            content = json.dumps(res_data, indent=2)

    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="reviewer",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=[],
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )
