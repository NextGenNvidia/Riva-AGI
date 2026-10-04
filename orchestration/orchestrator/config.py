import os
from typing import Literal, List

AgentLevel = Literal["CEO", "MANAGER", "TASK_DOER"]

ROLE_ALIASES = {
    "DEVOPS": ["GEMINI_API_KEY_DEVOPS", "GEMINI_API_KEY_WORKER_8"],
    "QA_TESTER": ["GEMINI_API_KEY_QA_TESTER", "GEMINI_API_KEY_WORKER_6"],
    "DATA_ANALYST": ["GEMINI_API_KEY_DATA_ANALYST", "GEMINI_API_KEY_WORKER_7"],
    "DESIGNER": ["GEMINI_API_KEY_DESIGNER", "GEMINI_API_KEY_WORKER_5"],
    "SECURITY_AUDITOR": ["GEMINI_API_KEY_SECURITY_AUDITOR", "GEMINI_API_KEY_WORKER_9"],
    "SEO_SPECIALIST": ["GEMINI_API_KEY_SEO_SPECIALIST", "GEMINI_API_KEY_WORKER_10"],
}


class KeyManager:
    """
    Manages the 15 Gemini API keys assigned to the Agentic Company hierarchy.
    Reads from environment variables, provides keys per role, and supports key rotation.
    """
    
    def __init__(self):
        pass

    def get_api_key_for_role(self, role: str) -> str:
        """
        Retrieves the exact API key for the given role, checking aliases and global fallbacks.
        """
        role_upper = role.upper()
        
        # Check specific alias list if defined
        if role_upper in ROLE_ALIASES:
            for env_var in ROLE_ALIASES[role_upper]:
                val = os.getenv(env_var, "").strip()
                if val:
                    return val
                    
        # Check direct env var
        direct_var = f"GEMINI_API_KEY_{role_upper}"
        val = os.getenv(direct_var, "").strip()
        if val:
            return val
            
        # Fallback to global GEMINI_API_KEY or any available key
        global_key = os.getenv("GEMINI_API_KEY", "").strip()
        if global_key:
            return global_key
            
        all_keys = self.get_all_available_keys()
        return all_keys[0] if all_keys else ""

    def get_all_available_keys(self) -> List[str]:
        """
        Returns a list of all distinct non-empty API keys configured in the environment.
        """
        keys = []
        for k, v in os.environ.items():
            if k.startswith("GEMINI_API_KEY") and v.strip():
                if v.strip() not in keys:
                    keys.append(v.strip())
        return keys

    def get_fallback_keys(self, current_key: str) -> List[str]:
        """
        Returns other available keys excluding the current one (useful for 429 quota rotation).
        """
        return [k for k in self.get_all_available_keys() if k != current_key]


# Singleton instance to be used by the Orchestrator/Agent Factory
key_manager = KeyManager()
