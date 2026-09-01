import logging
import os
import platform
import re
import subprocess
from typing import List, Optional
from orchestration.tools.registry import tool

logger = logging.getLogger(__name__)

# Security blacklist of dangerous commands/patterns
_DANGEROUS_SUBSTRINGS: List[str] = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf *",
    "rmdir /s /q",
    "del /f /s /q",
    "del /s /q",
    "del /q /s",
    "format c:",
    "mkfs",
    "shutdown",
    ":(){ :|:& };:",
    "dd if=",
]

_DANGEROUS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+-[rf]{1,2}\s+[/~*]", re.IGNORECASE),
    re.compile(r"\brmdir\s+.*[/\\][sq]", re.IGNORECASE),
    re.compile(r"\bdel\s+.*[/\\][fsq]", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bshutdown(\.exe)?\b", re.IGNORECASE),
    re.compile(r"\bmkfs(\.[a-z0-9]+)?\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
]


def _is_dangerous_command(command: str) -> bool:
    """Checks if a command contains dangerous or destructive instructions."""
    cmd_lower = command.lower().strip()
    for item in _DANGEROUS_SUBSTRINGS:
        if item in cmd_lower:
            return True
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return True
    return False


@tool(category="system")
def execute_command(command: str, timeout_seconds: int = 30) -> str:
    """Executes terminal commands safely using subprocess.

    Args:
        command: The terminal command to execute.
        timeout_seconds: Maximum time allowed for command execution in seconds (default: 30).

    Returns:
        Formatted string containing exit code, stdout, and stderr, or an error message.
    """
    if not command or not command.strip():
        return "Error: Command cannot be empty."

    if _is_dangerous_command(command):
        logger.warning(f"Blocked dangerous command from execution: {command}")
        return f"Error: Command blocked by security blacklist: '{command}'"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        stdout_str = result.stdout.strip() if result.stdout else "(empty)"
        stderr_str = result.stderr.strip() if result.stderr else "(empty)"
        return (
            f"Exit Code: {result.returncode}\n"
            f"Stdout:\n{stdout_str}\n"
            f"Stderr:\n{stderr_str}"
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Command '{command}' timed out after {timeout_seconds} seconds.")
        return f"Error: Command timed out after {timeout_seconds} seconds."
    except Exception as e:
        logger.error(f"Error executing command '{command}': {e}")
        return f"Error executing command: {str(e)}"


@tool(category="system")
def get_system_info() -> str:
    """Returns details about the host operating system, release, Python version, and working directory.

    Returns:
        Formatted string with system information.
    """
    try:
        info_lines = [
            f"OS Platform: {platform.system()}",
            f"OS Release: {platform.release()}",
            f"OS Version: {platform.version()}",
            f"Python Version: {platform.python_version()}",
            f"Current Working Directory: {os.getcwd()}",
        ]
        return "\n".join(info_lines)
    except Exception as e:
        logger.error(f"Error retrieving system info: {e}")
        return f"Error retrieving system info: {str(e)}"
