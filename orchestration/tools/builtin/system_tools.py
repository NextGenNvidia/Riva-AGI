"""
System & Utility Tools — orchestration/tools/builtin/system_tools.py
====================================================================
General utility tools for math, system status, and time operations.
"""

import datetime
import math
import os
import platform
from orchestration.tools.base import tool
from orchestration.tools.registry import tool_registry


@tool(
    name="get_current_time",
    description="Get the current system date, time, timezone, and day of the week.",
    category="system",
    tags=["time", "date", "clock"],
)
def get_current_time() -> str:
    """Returns current date and time ISO formatted."""
    now = datetime.datetime.now()
    return f"Current System Time: {now.strftime('%Y-%m-%d %H:%M:%S (%A)')}"


@tool(
    name="calculate",
    description="Safely evaluate a mathematical expression (supports arithmetic, math module functions).",
    category="system",
    tags=["math", "calculation", "calculator"],
)
def calculate(expression: str) -> str:
    """Evaluates mathematical expression safely."""
    safe_dict = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
    safe_dict.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow})
    try:
        # Prevent arbitrary code injection
        clean_expr = expression.replace("__", "")
        result = eval(clean_expr, {"__builtins__": {}}, safe_dict)
        return f"Result: {result}"
    except Exception as e:
        return f"Calculation Error: {str(e)}"


@tool(
    name="get_system_info",
    description="Get basic system environment information (OS, Python version, platform).",
    category="system",
    tags=["system", "info", "env"],
)
def get_system_info() -> str:
    """Returns system environment info."""
    return (
        f"OS: {platform.system()} {platform.release()}\n"
        f"Architecture: {platform.machine()}\n"
        f"Python Version: {platform.python_version()}\n"
        f"Working Directory: {os.getcwd()}"
    )


# Register system tools
tool_registry.register(get_current_time)
tool_registry.register(calculate)
tool_registry.register(get_system_info)
