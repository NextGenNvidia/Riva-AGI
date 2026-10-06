# API Integrations Track (Track 4)

**Contributors:** Garima Singh, Vaishali Singh

## Purpose

This directory is the dedicated workspace for the Integration/APIs track. All external SaaS connectors, third-party REST clients, webhook handlers, and enterprise API adapters belong here.

## Architecture Rule

Every integration agent must register with the root orchestrator via the standard `AgentRegistry` contract. **Do NOT modify** `orchestration/orchestrator/` internals directly.

### Registration Example

```python
from orchestration.orchestrator.registry import registry, AgentCapabilities
from orchestration import InputData, AgentResponse, ResponseStatus

@registry.register(
    "external_api_agent",
    AgentCapabilities(
        description="Handles third-party API queries.",
        tools=["fetch_external_data"],
        agent_level="TASK_DOER"
    )
)
def external_api_agent(task_data: InputData) -> AgentResponse:
    # Execute API call and return structured response
    return AgentResponse(
        agent_id="external_api_agent",
        status=ResponseStatus.SUCCESS,
        content="API result here",
        tool_calls=[],
    )
```

## Contract

- **Input:** `InputData` (text_content, input_type, metadata)
- **Output:** `AgentResponse` (agent_id, status, content, tool_calls)
- **Registration:** Via `@registry.register()` decorator

## Guidelines

1. Each integration should be a separate Python module inside this directory.
2. Use environment variables for all API keys and secrets (never hardcode).
3. Handle rate limits, timeouts, and retries gracefully within your module.
4. Write unit tests in `tests/unit/` following the existing test patterns.
