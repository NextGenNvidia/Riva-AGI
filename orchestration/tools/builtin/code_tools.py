"""
Code Execution & Development Tools — orchestration/tools/builtin/code_tools.py
================================================================================
Empowers Riva-AGI agents (specifically Coder Agent) to write, test, validate,
and debug Python code autonomously.
"""

import ast
import subprocess
import sys
import tempfile
from pathlib import Path
from orchestration.tools.base import tool
from orchestration.tools.registry import tool_registry


@tool(
    name="execute_python_code",
    description="Execute Python code in an isolated subprocess and return stdout, stderr, and exit status. Has a timeout safety guardrail.",
    category="code",
    tags=["python", "execution", "coder"],
)
def execute_python_code(code: str, timeout_seconds: int = 15) -> str:
    """Executes Python code and captures output."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        code_status = f"[Exit Code {result.returncode}]"

        output_parts = [code_status]
        if out:
            output_parts.append(f"STDOUT:\n{out}")
        if err:
            output_parts.append(f"STDERR:\n{err}")
        if not out and not err:
            output_parts.append("(Code executed successfully with no output)")

        return "\n\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"Execution Error: Timed out after {timeout_seconds} seconds."
    except Exception as e:
        return f"Execution Error: {str(e)}"
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass


@tool(
    name="check_python_syntax",
    description="Validate Python code syntax using AST parsing without executing it. Returns syntax errors or confirmation.",
    category="code",
    tags=["syntax", "validation", "linting"],
)
def check_python_syntax(code: str) -> str:
    """Parses code with ast to detect syntax errors before execution."""
    try:
        ast.parse(code)
        return "Syntax Validation: PASSED (No syntax errors detected)."
    except SyntaxError as e:
        return f"Syntax Error on line {e.lineno}, col {e.offset}: {e.msg}\nCode line: {e.text}"
    except Exception as e:
        return f"Syntax Check Error: {str(e)}"


@tool(
    name="run_pytest",
    description="Run pytest test suite or a specific test file/test case.",
    category="code",
    tags=["testing", "pytest", "unit-test"],
)
def run_pytest(test_target: str = "tests", flags: str = "-v") -> str:
    """Runs pytest on the specified target."""
    cmd = [sys.executable, "-m", "pytest", test_target] + flags.split()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = (result.stdout + "\n" + result.stderr).strip()
        status = "PASSED" if result.returncode == 0 else f"FAILED (Exit Code {result.returncode})"
        return f"Pytest Status: {status}\n\n{output}"
    except subprocess.TimeoutExpired:
        return "Pytest Error: Test run timed out after 30 seconds."
    except Exception as e:
        return f"Pytest Error: {str(e)}"


# Register code tools
tool_registry.register(execute_python_code)
tool_registry.register(check_python_syntax)
tool_registry.register(run_pytest)
