"""
Researcher Agent — orchestration/agents/researcher.py
======================================================
Autonomous research agent capable of executing web searches,
fetching URL content, inspecting directories, and synthesizing findings.
"""
import logging
import time
from typing import List

from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini
from orchestration.orchestrator.schemas.tool import ToolCall

logger = logging.getLogger(__name__)

RESEARCHER_TOOLS = [
    "web_search",
    "fetch_url_content",
    "read_file",
    "list_directory",
    "inspect_browser_dom",
    "navigate_browser",
]


@registry.register("researcher", AgentCapabilities(description="Handles internet research, documentation extraction, and data gathering.", tools=RESEARCHER_TOOLS, agent_level="TASK_DOER"))
def researcher_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Researcher Agent")
    start_time = time.time()
    
    prompt_text = task_data.text_content or ""
    my_key = key_manager.get_api_key_for_role("RESEARCHER")
    
    sys_prompt = (
        "You are the Principal Intelligence & Research Specialist (Researcher Agent) in the Riva-AGI framework.\n"
        "Your mission is to gather real-time internet intelligence, extract documentation, synthesize facts, and provide verified research deliverables.\n\n"
        "OPERATIONAL PROTOCOLS:\n"
        "1. Active Tool Execution: You have direct access to tools: web_search, fetch_url_content, read_file, and list_directory. "
        "Actively search the web for fresh data and fetch specific URLs to extract authoritative content rather than guessing.\n"
        "2. Multi-Source Verification: Cross-reference findings across multiple sources to ensure accuracy, objectivity, and recency.\n"
        "3. Citation & Grounding: Ground all statements in verified sources. Include explicit URLs and source citations for key facts, benchmarks, and claims.\n"
        "4. Deep Extraction: When a search returns promising links, use fetch_url_content to inspect the actual webpage text for technical details and specifics.\n"
        "5. Output Structure: Present deliverables in an executive format: Executive Summary, Key Findings / Technical Analysis, Strategic Takeaways, and References/Citations."
    )
    
    try:
        content, tool_calls = call_gemini(
            prompt=prompt_text, 
            api_key=my_key, 
            system_instruction=sys_prompt, 
            agent_id="researcher",
            tools=RESEARCHER_TOOLS,
            return_tool_calls=True
        )
    except Exception as e:
        logger.error(f"Researcher LLM generation failed: {e}")
        content = f"Research Error: {e}"
        tool_calls = []

    content = content or ""
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="researcher",
        status=ResponseStatus.SUCCESS if not content.startswith("Research Error") else ResponseStatus.FAILURE,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value, "tools_used": len(tool_calls)}
    )