import pytest
from unittest.mock import MagicMock, patch
from orchestration.orchestrator.llm import _wrap_tool_for_execution, call_gemini
from orchestration.orchestrator.schemas.tool import ToolCall
from orchestration.tools import tool_registry
from orchestration import InputData, InputType
from orchestration.agents.coder import coder_agent
from orchestration.agents.researcher import researcher_agent


def test_tool_wrapper_tracking():
    executed_log = []
    
    def sample_tool(text: str, repeat: int = 1) -> str:
        """Sample function for testing."""
        return text * repeat

    wrapped = _wrap_tool_for_execution("sample_tool", sample_tool, executed_log)
    result = wrapped(text="abc", repeat=3)
    
    assert result == "abcabcabc"
    assert len(executed_log) == 1
    call = executed_log[0]
    assert isinstance(call, ToolCall)
    assert call.tool_name == "sample_tool"
    assert call.parameters == {"text": "abc", "repeat": 3}


def test_tool_wrapper_error_handling():
    executed_log = []
    
    def faulty_tool():
        raise RuntimeError("Something failed")

    wrapped = _wrap_tool_for_execution("faulty_tool", faulty_tool, executed_log)
    result = wrapped()
    
    assert "Tool Execution Error" in result
    assert "Something failed" in result
    assert len(executed_log) == 1
    assert executed_log[0].tool_name == "faulty_tool"


@patch("orchestration.orchestrator.llm.genai.Client")
def test_call_gemini_with_tools(mock_client_cls):
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "File successfully created."
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    mock_client_cls.return_value = mock_client
    
    content, tool_calls = call_gemini(
        prompt="Create test.txt with hello",
        api_key="test_api_key",
        system_instruction="You are a coder.",
        agent_id="coder",
        tools=["write_file", "read_file"],
        return_tool_calls=True
    )
    
    assert content == "File successfully created."
    assert mock_client.chats.create.called
    call_args = mock_client.chats.create.call_args[1]
    assert call_args["config"].tools is not None
    assert len(call_args["config"].tools) == 2


@patch("orchestration.agents.coder.call_gemini")
@patch("orchestration.agents.coder.key_manager.get_api_key_for_role")
def test_coder_agent_returns_tool_calls(mock_get_key, mock_call_gemini):
    mock_get_key.return_value = "fake_key"
    mock_call = ToolCall(
        call_id="call_123",
        tool_name="write_file",
        parameters={"file_path": "app.py", "content": "print('hello')"},
        expected_return_type="str"
    )
    mock_call_gemini.return_value = ("I have created app.py", [mock_call])
    
    input_data = InputData(input_type=InputType.TEXT, text_content="Create app.py")
    response = coder_agent(input_data)
    
    assert response.agent_id == "coder"
    assert response.content == "I have created app.py"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "write_file"
