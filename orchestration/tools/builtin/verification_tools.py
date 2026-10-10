"""
Verification & Test Diagnostics Agent Tools for Riva-AGI.
=========================================================
Equips autonomous agents (coder, qa_tester) with tools to verify code syntax,
execute test suites, and diagnose failure tracebacks before declaring tasks complete.
"""

import logging
import os
from typing import Optional

from orchestration.tools.registry import tool
from orchestration.verification.verifier import CodeVerifier

logger = logging.getLogger("orchestration.tools.verification")


@tool(category="verification")
def verify_code_syntax(file_path: str) -> str:
    """Statically verifies the Python AST syntax of a source file without executing it.

    Args:
        file_path: Relative or absolute path to the Python source file.

    Returns:
        Structured string indicating whether syntax is valid, or specific line numbers and syntax error messages.
    """
    clean_path = (file_path or "").strip()
    if not clean_path:
        return "Error: file_path must not be empty."

    if not os.path.exists(clean_path):
        return f"Error: File does not exist at '{clean_path}'."

    res = CodeVerifier.verify_syntax(clean_path)
    return res.to_summary()


@tool(category="verification")
def run_code_tests(test_path: str, timeout_seconds: int = 30) -> str:
    """Executes a test file or directory using pytest in an isolated subprocess.

    Args:
        test_path: Path to the test file or test directory (e.g. 'tests/unit/test_foo.py').
        timeout_seconds: Maximum test run duration in seconds (default: 30).

    Returns:
        Structured string with test pass/fail outcome, exit code, and captured pytest output.
    """
    clean_path = (test_path or "").strip()
    if not clean_path:
        return "Error: test_path must not be empty."

    if not os.path.exists(clean_path):
        return f"Error: Test target does not exist at '{clean_path}'."

    try:
        timeout = int(timeout_seconds)
    except (ValueError, TypeError):
        timeout = 30

    res = CodeVerifier.run_tests(clean_path, timeout_seconds=timeout)
    status_str = "PASSED" if res.passed else "FAILED"
    output_lines = [
        f"Test Execution Result: {status_str} (Exit Code: {res.exit_code}, Duration: {res.duration_seconds:.2f}s)",
        f"Summary: {res.summary}",
    ]

    if not res.passed:
        # Include diagnosis directly
        combined = f"{res.stdout}\n{res.stderr}"
        diag = CodeVerifier.diagnose_failure(combined, exit_code=res.exit_code)
        output_lines.append(f"\nDiagnosis:\n{diag.format_repair_prompt(target_file=clean_path)}")
    else:
        output_lines.append(f"\nStdout Output:\n{res.stdout.strip()}")

    return "\n".join(output_lines)


@tool(category="verification")
def diagnose_test_failure(test_output: str) -> str:
    """Analyzes captured test failure output or traceback to extract root causes and actionable fix advice.

    Args:
        test_output: Raw stdout/stderr text from a failed test run or exception traceback.

    Returns:
        Structured repair prompt with error classification, failed test names, and suggested fixes.
    """
    clean_text = (test_output or "").strip()
    if not clean_text:
        return "Error: test_output must not be empty."

    diag = CodeVerifier.diagnose_failure(clean_text, exit_code=1)
    return diag.format_repair_prompt()
