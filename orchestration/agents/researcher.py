import logging
import time
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus
from orchestration.orchestrator.config import key_manager
from orchestration.orchestrator.llm import call_gemini

logger = logging.getLogger(__name__)

RESEARCHER_TOOLS = [
    "search_knowledge_base",
    "query_knowledge_with_citations",
    "list_knowledge_documents",
    "web_search",
    "fetch_url_content",
    "read_file",
    "list_directory",
]


@registry.register(
    "researcher",
    AgentCapabilities(
        description="Handles internet research, internal vector knowledge base retrieval, and document Q&A.",
        tools=RESEARCHER_TOOLS,
        agent_level="TASK_DOER",
    ),
)
def researcher_agent(task_data: InputData) -> AgentResponse:
    logger.info("Routing to Researcher Agent")
    
    start_time = time.time()
    my_key = key_manager.get_api_key_for_role("RESEARCHER")
    
    sys_prompt = (
        "You are the Researcher Agent in the Riva-AGI autonomous system.\n"
        "You have access to both internal knowledge base tools and external research tools:\n"
        "- Internal Knowledge: search_knowledge_base, query_knowledge_with_citations, list_knowledge_documents.\n"
        "- Web & Filesystem: web_search, fetch_url_content, read_file, list_directory.\n"
        "When asked about internal projects, schedules, guidelines, policies, or uploaded documents, ALWAYS query the knowledge base first.\n"
        "When asked for external or current web information, use web_search and fetch_url_content.\n"
        "Synthesize facts accurately and always provide clear citations and source references."
    )
    
    content, tool_calls = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="researcher",
        tools=RESEARCHER_TOOLS,
        return_tool_calls=True
    )
    
    execution_time = (time.time() - start_time) * 1000
    
    return AgentResponse(
        agent_id="researcher",
        status=ResponseStatus.SUCCESS,
        content=content,
        tool_calls=tool_calls,
        execution_time_ms=execution_time,
        metadata={"processed_modality": task_data.input_type.value}
    )