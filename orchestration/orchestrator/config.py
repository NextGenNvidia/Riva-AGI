import os
import random
from typing import Literal

AgentLevel = Literal["CEO", "MANAGER", "TASK_DOER"]

class KeyManager:
    """
    Manages the 15 Gemini API keys assigned to the Agentic Company hierarchy.
    Reads from environment variables and provides keys based on the exact agent's role.
    """
    
    def __init__(self):
        # load_dotenv() is assumed to be called at the entrypoint (main.py)
        pass

    def get_api_key_for_role(self, role: str) -> str:
        """
        Retrieves the exact API key for the given role.
        E.g., "ORCHESTRATOR" -> GEMINI_API_KEY_ORCHESTRATOR
        E.g., "CODER" -> GEMINI_API_KEY_CODER
        """
        env_var_name = f"GEMINI_API_KEY_{role.upper()}"
        return os.getenv(env_var_name, "")

# Singleton instance to be used by the Orchestrator/Agent Factory
key_manager = KeyManager()
