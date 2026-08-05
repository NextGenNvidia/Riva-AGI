from orchestration.agents.coder import coder_agent
from orchestration.agents.researcher import researcher_agent


AGENT_REGISTRY = {
    "coder": coder_agent,
    "researcher": researcher_agent,
}