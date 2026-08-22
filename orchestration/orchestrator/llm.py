import logging
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

# Define the Multi-Model Architecture Mapping
MODEL_MAPPING = {
    # Level 2 Managers (High Reasoning & Orchestration)
    "intent_classifier": "gemini-3.5-flash-lite",  # Called frequently, needs high RPM
    "executor": "gemini-3.5-flash-lite",           # Called frequently in loops
    "planner": "gemini-3.0-flash",                   # Deep reasoning, called once
    "reviewer": "gemini-3.0-flash",                  # Deep reasoning, called once
    
    # Level 3 Complex Workers (Balanced)
    "coder": "gemini-3.1-flash-lite",
    "reasoner": "gemini-3.1-flash-lite",
    "devops": "gemini-3.1-flash-lite",
    "security_auditor": "gemini-3.1-flash-lite",
    
    # Level 3 Standard Workers (Fast Execution)
    "writer": "gemini-3.5-flash-lite",
    "designer": "gemini-3.5-flash-lite",
    "qa_tester": "gemini-3.1-flash-lite",
    "data_analyst": "gemini-3.1-flash-lite",
    "seo_specialist": "gemini-3.1-flash-lite",
    "researcher": "gemini-3.5-flash-lite",
    "dummy_system": "gemini-3.5-flash-lite"
}

def call_gemini(prompt: str, api_key: str, system_instruction: str, agent_id: str) -> str:
    """
    Calls the Google GenAI SDK using the specific model assigned to the agent.
    If the specified model fails (e.g., if a future model name is not yet active in the API), 
    it falls back to standard gemini-2.5-flash to ensure resilience.
    """
    if not api_key:
        return "ERROR: API Key is missing for this agent."
        
    model_name = MODEL_MAPPING.get(agent_id, "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.7,
    )
    
    try:
        logger.info(f"Agent [{agent_id}] triggering LLM -> {model_name}")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        return response.text
    except APIError as e:
        logger.warning(f"Agent [{agent_id}] failed with model {model_name}: {e}. Falling back to gemini-3.5-flash-lite")
        try:
            # Fallback for experimental or unavailable models
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as fallback_e:
            return f"LLM Generation Failed on Fallback: {fallback_e}"
    except Exception as e:
        return f"LLM Generation Error: {e}"
