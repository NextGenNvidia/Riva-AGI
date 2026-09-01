import subprocess
from unittest.mock import patch
import pytest

from orchestration.tools.builtin.system_tools import (
    execute_command,
    get_system_info,
    _is_dangerous_command,
)
from orchestration.tools.registry import tool_registry


def test_system_tools_registered():
    """Verify that system tools are registered in tool_registry."""
    assert tool_registry.get_tool("execute_command") is not None
    assert tool_registry.get_tool("get_system_info") is not None

    exec_def = tool_registry.get_tool_definition("execute_command")
    assert exec_def.category == "system"
    assert "command" in exec_def.parameters_schema

    sys_def = tool_registry.get_tool_definition("get_system_info")
    assert sys_def.category == "system"


def test_get_system_info():
    """Test get_system_info returns expected system metadata."""
    info = get_system_info()
    assert isinstance(info, str)
    assert len(info) > 0
    assert "OS Platform:" in info
    assert "OS Release:" in info
    assert "Python Version:" in info
    assert "Current Working Directory:" in info


def test_execute_command_success():
    """Test execute_command executes a simple Python command successfully."""
    result = execute_command('python -c "print(\'riva_system_test\')"')
    assert "Exit Code: 0" in result
    assert "Stdout:" in result
    assert "riva_system_test" in result


def test_execute_command_empty():
    """Test execute_command with empty string."""
    result = execute_command("   ")
    assert "Error: Command cannot be empty." in result


@pytest.mark.parametrize(
    "bad_cmd",
    [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rmdir /s /q c:",
        "rmdir /s /q c:\\",
        "del /f /s /q c:",
        "del /s /q c:\\test",
        "format c:",
        "format d:",
        "shutdown",
        "shutdown.exe /s /t 0",
        "mkfs",
        "mkfs.ext4 /dev/sda",
        ":(){ :|:& };:",
        "dd if=/dev/zero of=/dev/sda",
    ],
)
def test_execute_command_blacklist(bad_cmd: str):
    """Test that security blacklist blocks destructive commands."""
    assert _is_dangerous_command(bad_cmd) is True
    result = execute_command(bad_cmd)
    assert "Error: Command blocked by security blacklist:" in result
    assert bad_cmd in result


def test_execute_command_timeout():
    """Test execute_command timeout handling."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep 10", timeout=1)):
        result = execute_command("sleep 10", timeout_seconds=1)
        assert "Error: Command timed out after 1 seconds." in result


def test_execute_command_general_exception():
    """Test execute_command handles unexpected subprocess errors."""
    with patch("subprocess.run", side_effect=RuntimeError("Subprocess execution failed")):
        result = execute_command("echo hello")
        assert "Error executing command: Subprocess execution failed" in result
