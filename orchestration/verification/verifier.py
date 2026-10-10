"""
Autonomous Code Verification & Diagnostic Engine for Riva-AGI.
==============================================================
Provides static AST syntax validation, sandboxed pytest execution,
and automated test failure diagnosis for the self-healing coding loop.
"""

import ast
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("orchestration.verification.verifier")


@dataclass
class SyntaxVerificationResult:
    """Outcome of static Python syntax & AST validation."""
    valid: bool
    error_message: Optional[str] = None
    line_number: Optional[int] = None
    offset: Optional[int] = None
    source_file: Optional[str] = None

    def to_summary(self) -> str:
        if self.valid:
            target = f" in '{self.source_file}'" if self.source_file else ""
            return f"Syntax Valid: Python code{target} is syntactically sound and parsed successfully."
        line_str = f" at line {self.line_number}" if self.line_number else ""
        col_str = f", column {self.offset}" if self.offset else ""
        return f"Syntax Error{line_str}{col_str}: {self.error_message}"


@dataclass
class TestExecutionResult:
    """Outcome of subprocess test suite execution."""
    __test__ = False
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    summary: str = ""
    test_target: str = ""


@dataclass
class FailureDiagnosis:
    """Actionable diagnosis extracted from test failure output."""
    has_failures: bool
    failure_type: str
    failed_tests: List[str] = field(default_factory=list)
    traceback_snippet: str = ""
    root_cause: str = ""
    suggestion: str = ""

    def format_repair_prompt(self, target_file: Optional[str] = None) -> str:
        """Formats an actionable repair prompt for the autonomous coder agent."""
        if not self.has_failures:
            return "No failures detected. All tests passed."

        lines = [
            "AUTOMATED TEST-DRIVEN REPAIR DIAGNOSTIC:",
            f"Failure Classification: {self.failure_type}",
            f"Failed Test Assertions: {', '.join(self.failed_tests) if self.failed_tests else 'General test failure'}",
        ]
        if self.root_cause:
            lines.append(f"Root Cause: {self.root_cause}")
        if self.traceback_snippet:
            lines.append(f"Relevant Traceback:\n```\n{self.traceback_snippet.strip()}\n```")
        if self.suggestion:
            lines.append(f"Recommended Fix: {self.suggestion}")
        if target_file:
            lines.append(f"Target File to Fix: {target_file}")
        lines.append("Instruction: Analyze the failure above and edit the code to satisfy all tests.")
        return "\n".join(lines)


class CodeVerifier:
    """Static and dynamic code verification suite for autonomous agents."""

    @staticmethod
    def verify_syntax(code_or_file_path: str) -> SyntaxVerificationResult:
        """Validates Python syntax statically using AST compilation without executing code.

        Args:
            code_or_file_path: Python source code string OR path to a .py file.

        Returns:
            SyntaxVerificationResult indicating validity or line-specific error details.
        """
        source_code = code_or_file_path
        source_file = None

        # Check if argument is an existing file path
        if os.path.exists(code_or_file_path) and os.path.isfile(code_or_file_path):
            source_file = code_or_file_path
            try:
                with open(code_or_file_path, "r", encoding="utf-8") as f:
                    source_code = f.read()
            except Exception as e:
                return SyntaxVerificationResult(
                    valid=False,
                    error_message=f"Failed to read file: {e}",
                    source_file=source_file,
                )

        try:
            ast.parse(source_code, filename=source_file or "<string>")
            return SyntaxVerificationResult(valid=True, source_file=source_file)
        except SyntaxError as syn_err:
            return SyntaxVerificationResult(
                valid=False,
                error_message=syn_err.msg,
                line_number=syn_err.lineno,
                offset=syn_err.offset,
                source_file=source_file,
            )
        except Exception as exc:
            return SyntaxVerificationResult(
                valid=False,
                error_message=str(exc),
                source_file=source_file,
            )

    @staticmethod
    def run_tests(
        test_target: str,
        timeout_seconds: int = 30,
        cwd: Optional[str] = None,
        python_executable: Optional[str] = None,
    ) -> TestExecutionResult:
        """Executes a test target using pytest in an isolated subprocess.

        Args:
            test_target: Path to test file, test directory, or pytest node ID.
            timeout_seconds: Maximum execution time before aborting (default: 30s).
            cwd: Working directory (defaults to current working directory).
            python_executable: Path to python executable (defaults to sys.executable).

        Returns:
            TestExecutionResult containing pass/fail state, exit code, stdout, and stderr.
        """
        py_exec = python_executable or sys.executable
        work_dir = cwd or os.getcwd()
        clean_target = (test_target or "").strip()

        if not clean_target:
            return TestExecutionResult(
                passed=False,
                exit_code=1,
                stdout="",
                stderr="No test target specified.",
                duration_seconds=0.0,
                summary="Error: Test target path is empty.",
                test_target=test_target,
            )

        cmd = [py_exec, "-m", "pytest", clean_target, "-v"]
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
            )
            duration = time.time() - start_time
            passed = result.returncode == 0
            stdout_str = result.stdout or ""
            stderr_str = result.stderr or ""

            # Extract pytest summary line if present
            summary = ""
            for line in reversed(stdout_str.splitlines()):
                if "passed" in line or "failed" in line or "error" in line:
                    summary = line.strip()
                    break
            if not summary:
                summary = "Tests completed with exit code 0" if passed else f"Tests failed with exit code {result.returncode}"

            return TestExecutionResult(
                passed=passed,
                exit_code=result.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                summary=summary,
                test_target=clean_target,
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return TestExecutionResult(
                passed=False,
                exit_code=124,
                stdout="",
                stderr=f"Test execution timed out after {timeout_seconds} seconds.",
                duration_seconds=duration,
                summary=f"Timeout: Tests exceeded {timeout_seconds}s limit.",
                test_target=clean_target,
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestExecutionResult(
                passed=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=duration,
                summary=f"Subprocess Error: {e}",
                test_target=clean_target,
            )

    @staticmethod
    def diagnose_failure(test_output: str, exit_code: int = 1) -> FailureDiagnosis:
        """Parses pytest or python tracebacks and produces structured, actionable repair diagnoses.

        Args:
            test_output: Combined stdout/stderr from test run.
            exit_code: Process return code.

        Returns:
            FailureDiagnosis with extracted test names, traceback snippets, and fix suggestions.
        """
        if exit_code == 0 and ("FAILED" not in test_output and "ERROR" not in test_output):
            return FailureDiagnosis(
                has_failures=False,
                failure_type="NONE",
                suggestion="All tests passed successfully.",
            )

        # 1. Identify failed test names (e.g., FAILED tests/unit/test_foo.py::test_bar)
        failed_tests = re.findall(r"(?:FAILED|ERROR)\s+([^\s:]+(?:::[\w_]+)?)", test_output)

        # 2. Identify failure classification
        failure_type = "TEST_ASSERTION_FAILURE"
        suggestion = "Review failed assertions and align implementation logic with test expectations."

        if "SyntaxError" in test_output:
            failure_type = "SYNTAX_ERROR"
            suggestion = "Fix syntax error (unclosed brackets, invalid indentation, or typo)."
        elif "ImportError" in test_output or "ModuleNotFoundError" in test_output:
            failure_type = "IMPORT_ERROR"
            suggestion = "Verify module imports, package paths, and circular dependency issues."
        elif "TypeError" in test_output:
            failure_type = "TYPE_ERROR"
            suggestion = "Check function parameter counts, type signatures, and return value types."
        elif "IndexError" in test_output or "KeyError" in test_output:
            failure_type = "BOUNDARY_ERROR"
            suggestion = "Check list bounds, dictionary keys, and handle empty sequence edge cases."
        elif "timed out" in test_output.lower():
            failure_type = "TIMEOUT"
            suggestion = "Optimize time complexity or eliminate infinite loops/blocking I/O."

        # 3. Extract most relevant traceback snippet
        traceback_snippet = ""
        lines = test_output.splitlines()
        tb_lines = []
        capturing = False
        for line in lines:
            if "Traceback (most recent call last):" in line or line.startswith("E   "):
                capturing = True
            if capturing:
                tb_lines.append(line)
                if len(tb_lines) >= 15:
                    break
        if tb_lines:
            traceback_snippet = "\n".join(tb_lines)
        else:
            # Fall back to error snippet lines
            error_lines = [l for l in lines if l.startswith("E   ") or "FAILED" in l or "Error:" in l]
            traceback_snippet = "\n".join(error_lines[:10])

        # 4. Extract specific assertion failure message if available
        root_cause = ""
        for line in lines:
            if line.startswith("E   AssertionError:") or line.startswith("E   "):
                root_cause = line.strip()
                break

        return FailureDiagnosis(
            has_failures=True,
            failure_type=failure_type,
            failed_tests=failed_tests,
            traceback_snippet=traceback_snippet,
            root_cause=root_cause,
            suggestion=suggestion,
        )
