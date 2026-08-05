"""
Schemas Package — orchestrator/schemas/__init__.py
====================================================
Central re-export hub for all Pydantic schema models.

Any team can do:
    from orchestrator.schemas import InputData, ToolCall, AgentResponse

While individual teams only edit their own file:
    - Voice/Vision team  --> input.py
    - Agents/LLM team    --> tool.py
    - Orchestration team --> response.py

This eliminates merge conflicts across all 8 feature teams.
"""

# try/except handles TWO execution modes:
#   1. Relative imports (from .input) work when imported as a PACKAGE
#      e.g., from orchestrator.schemas import InputData
#   2. Direct imports (from input) work when run as a SCRIPT
#      e.g., python orchestrator/schemas/__init__.py
try:
    # --- Package mode (normal usage by other modules) ---
    from .input import InputType, MediaSourceType, MediaPayload, InputData
    from .tool import ToolCall, ToolResult
    from .response import ResponseStatus, AgentResponse
except ImportError:
    # --- Script mode (direct execution for testing) ---
    from input import InputType, MediaSourceType, MediaPayload, InputData
    from tool import ToolCall, ToolResult
    from response import ResponseStatus, AgentResponse


# __all__ controls what gets exported when someone does `from orchestrator.schemas import *`
__all__ = [
    # Input
    "InputType",
    "MediaSourceType",
    "MediaPayload",
    "InputData",
    # Tool
    "ToolCall",
    "ToolResult",
    # Response
    "ResponseStatus",
    "AgentResponse",
]


# ============================================================================
# VERIFICATION SCRIPT — runs only when executed directly
# ============================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("  Riva-AGI: Modular Schema Verification Script")
    print("=" * 65)

    # STEP 1: Create InputData with typed MediaPayload
    print("\n--- STEP 1: Creating InputData with MediaPayload ---")
    audio_payload = MediaPayload(
        source_type=MediaSourceType.URL,
        data="https://cdn.riva-agi.dev/audio/user_voice_123.wav",
        mime_type="audio/wav"
    )
    user_input = InputData(
        input_type=InputType.MULTIMODAL,
        text_content="Search for the latest weather in Tokyo and analyze this voice note.",
        audio_data=audio_payload,
        metadata={
            "user_id": "usr_98765",
            "mood_signals": {"sentiment": "curious", "urgency": "medium", "tone": "polite"},
            "session_id": "sess_abc_xyz"
        }
    )
    print("InputData schema validated successfully!")
    print(f"  Modality       : {user_input.input_type.value}")
    print(f"  Text Query     : {user_input.text_content}")
    print(f"  Audio Source   : {user_input.audio_data.source_type.value}")
    print(f"  Audio Data     : {user_input.audio_data.data}")
    print(f"  Audio MIME     : {user_input.audio_data.mime_type}")
    print(f"  Mood Sentiment : {user_input.metadata['mood_signals']['sentiment']}")

    # STEP 2: Agent creates a ToolCall
    print("\n--- STEP 2: Agent Creates a ToolCall ---")
    tool_call = ToolCall(
        call_id="call_weather_001",
        tool_name="get_current_weather",
        parameters={"location": "Tokyo, Japan", "units": "celsius"},
        expected_return_type="dict"
    )
    print("ToolCall schema created!")
    print(f"  Call ID        : {tool_call.call_id}")
    print(f"  Tool Name      : {tool_call.tool_name}")
    print(f"  Parameters     : {tool_call.parameters}")
    print(f"  Expected Return: {tool_call.expected_return_type}")

    # STEP 3: Agent packages its AgentResponse
    print("\n--- STEP 3: Agent Response to Root Orchestrator ---")
    agent_response = AgentResponse(
        agent_id="agent_weather_v1",
        status=ResponseStatus.NEEDS_TOOL_EXECUTION,
        content="I need to fetch live weather data before I can answer.",
        tool_calls=[tool_call],
        execution_time_ms=42.5,
        metadata={"model_used": "gemini-2.5-flash", "tokens_used": 150}
    )
    print("AgentResponse instance created successfully!")
    print(f"  Agent ID       : {agent_response.agent_id}")
    print(f"  Status         : {agent_response.status.value}")
    print(f"  Content        : {agent_response.content}")
    print(f"  Tool Calls     : {len(agent_response.tool_calls)} call(s)")

    # STEP 4: Orchestrator returns ToolResult
    print("\n--- STEP 4: Orchestrator Returns ToolResult ---")
    tool_result = ToolResult(
        call_id="call_weather_001",
        tool_name="get_current_weather",
        success=True,
        output={
            "location": "Tokyo, Japan",
            "temperature_celsius": 28,
            "condition": "Partly Cloudy",
            "humidity_percent": 65
        },
        execution_time_ms=310.7
    )
    print("ToolResult schema created!")
    print(f"  Call ID        : {tool_result.call_id}")
    print(f"  Tool Name      : {tool_result.tool_name}")
    print(f"  Success        : {tool_result.success}")
    print(f"  Output         : {tool_result.output}")
    print(f"  Exec Time (ms) : {tool_result.execution_time_ms}")

    # STEP 5: Serialized JSON outputs
    print("\n--- STEP 5: Serialized AgentResponse JSON ---")
    print(agent_response.model_dump_json(indent=2))

    print("\n--- STEP 6: Serialized ToolResult JSON ---")
    print(tool_result.model_dump_json(indent=2))

    print("\n" + "=" * 65)
    print("  All modular schemas validated and working perfectly!")
    print("=" * 65)
