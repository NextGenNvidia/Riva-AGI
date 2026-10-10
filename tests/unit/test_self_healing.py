"""
Unit Tests for Autonomous Code Verification & Self-Healing Coding Loop.
======================================================================
"""

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from orchestration.verification.verifier import (
    CodeVerifier,
    SyntaxVerificationResult,
    TestExecutionResult,
    FailureDiagnosis,
)
from orchestration.verification.self_healing import (
    SelfHealingController,
    SelfHealingResult,
)
from orchestration.tools.registry import tool_registry
import orchestration.tools.builtin
from orchestration.orchestrator.registry import registry
import orchestration.agents.coder
import orchestration.agents.qa_tester
from orchestration.tools.builtin.verification_tools import (
    verify_code_syntax,
    run_code_tests,
    diagnose_test_failure,
)


def test_verify_syntax_valid_code():
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    res = CodeVerifier.verify_syntax(code)
    assert res.valid is True
    assert res.error_message is None
    assert "Syntax Valid" in res.to_summary()


def test_verify_syntax_invalid_code():
    bad_code = "def broken(\n    return 42\n"
    res = CodeVerifier.verify_syntax(bad_code)
    assert res.valid is False
    assert res.error_message is not None
    assert res.line_number is not None
    assert "Syntax Error" in res.to_summary()


def test_verify_syntax_from_file():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write("x = 100\ny = x * 2\n")
        f_path = f.name

    try:
        res = CodeVerifier.verify_syntax(f_path)
        assert res.valid is True
        assert res.source_file == f_path
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


def test_verify_syntax_missing_file():
    res = CodeVerifier.verify_syntax("non_existent_file_xyz_123.py")
    # If not on disk, it treats it as source code string which might be valid or invalid syntax
    assert isinstance(res, SyntaxVerificationResult)


def test_run_tests_success_mock():
    mock_sub = MagicMock()
    mock_sub.returncode = 0
    mock_sub.stdout = "tests/test_calc.py::test_add PASSED\n\n=== 1 passed in 0.05s ==="
    mock_sub.stderr = ""

    with patch("subprocess.run", return_value=mock_sub):
        res = CodeVerifier.run_tests("tests/test_calc.py")
        assert res.passed is True
        assert res.exit_code == 0
        assert "1 passed" in res.summary


def test_run_tests_failure_mock():
    mock_sub = MagicMock()
    mock_sub.returncode = 1
    mock_sub.stdout = "tests/test_calc.py::test_add FAILED\n\n=== 1 failed in 0.05s ==="
    mock_sub.stderr = ""

    with patch("subprocess.run", return_value=mock_sub):
        res = CodeVerifier.run_tests("tests/test_calc.py")
        assert res.passed is False
        assert res.exit_code == 1
        assert "1 failed" in res.summary


def test_run_tests_timeout_handling():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=5)):
        res = CodeVerifier.run_tests("tests/test_calc.py", timeout_seconds=5)
        assert res.passed is False
        assert res.exit_code == 124
        assert "Timeout" in res.summary


def test_diagnose_failure_assertion_error():
    sample_traceback = """
============================= test session starts =============================
tests/unit/test_math.py::test_multiply FAILED                            [100%]

================================== FAILURES ===================================
________________________________ test_multiply ________________________________

    def test_multiply():
>       assert multiply(2, 3) == 6
E       AssertionError: assert 5 == 6
E         +  where 5 = multiply(2, 3)

tests/unit/test_math.py:6: AssertionError
=========================== short test summary info ===========================
FAILED tests/unit/test_math.py::test_multiply - AssertionError: assert 5 == 6
============================== 1 failed in 0.12s ===============================
"""
    diag = CodeVerifier.diagnose_failure(sample_traceback, exit_code=1)
    assert diag.has_failures is True
    assert diag.failure_type == "TEST_ASSERTION_FAILURE"
    assert any("test_multiply" in t for t in diag.failed_tests)
    assert "AssertionError" in diag.root_cause or "assert 5 == 6" in diag.root_cause

    prompt = diag.format_repair_prompt(target_file="math_lib.py")
    assert "AUTOMATED TEST-DRIVEN REPAIR DIAGNOSTIC" in prompt
    assert "Target File to Fix: math_lib.py" in prompt


def test_diagnose_failure_syntax_error():
    output = "SyntaxError: invalid syntax (calculator.py, line 12)"
    diag = CodeVerifier.diagnose_failure(output, exit_code=1)
    assert diag.has_failures is True
    assert diag.failure_type == "SYNTAX_ERROR"


def test_diagnose_failure_import_error():
    output = "ModuleNotFoundError: No module named 'utils'"
    diag = CodeVerifier.diagnose_failure(output, exit_code=1)
    assert diag.has_failures is True
    assert diag.failure_type == "IMPORT_ERROR"


def test_diagnose_failure_no_failures():
    output = "=== 5 passed in 0.23s ==="
    diag = CodeVerifier.diagnose_failure(output, exit_code=0)
    assert diag.has_failures is False
    assert diag.failure_type == "NONE"


def test_self_healing_cycle_first_try_pass():
    mock_verifier = MagicMock()
    mock_verifier.verify_syntax.return_value = SyntaxVerificationResult(valid=True)
    mock_verifier.run_tests.return_value = TestExecutionResult(
        passed=True, exit_code=0, stdout="OK", stderr="", duration_seconds=0.1, summary="1 passed"
    )

    controller = SelfHealingController(verifier=mock_verifier, max_iterations=3)
    repair_fn = MagicMock()

    result = controller.run_healing_cycle("foo.py", "test_foo.py", repair_fn)
    assert result.success is True
    assert result.iterations_count == 1
    repair_fn.assert_not_called()


def test_self_healing_cycle_repairs_bug():
    mock_verifier = MagicMock()
    mock_verifier.verify_syntax.return_value = SyntaxVerificationResult(valid=True)

    # First attempt fails, second attempt passes
    fail_res = TestExecutionResult(
        passed=False, exit_code=1, stdout="FAILED test_add", stderr="", duration_seconds=0.1, summary="1 failed"
    )
    pass_res = TestExecutionResult(
        passed=True, exit_code=0, stdout="PASSED test_add", stderr="", duration_seconds=0.1, summary="1 passed"
    )
    mock_verifier.run_tests.side_effect = [fail_res, pass_res]
    mock_verifier.diagnose_failure.return_value = FailureDiagnosis(
        has_failures=True, failure_type="TEST_ASSERTION_FAILURE", root_cause="assert 2 == 3"
    )

    controller = SelfHealingController(verifier=mock_verifier, max_iterations=3)
    repair_fn = MagicMock()

    result = controller.run_healing_cycle("foo.py", "test_foo.py", repair_fn)
    assert result.success is True
    assert result.iterations_count == 2
    assert repair_fn.call_count == 1


def test_self_healing_cycle_exhausts_max_iterations():
    mock_verifier = MagicMock()
    mock_verifier.verify_syntax.return_value = SyntaxVerificationResult(valid=True)
    fail_res = TestExecutionResult(
        passed=False, exit_code=1, stdout="FAILED", stderr="", duration_seconds=0.1, summary="1 failed"
    )
    mock_verifier.run_tests.return_value = fail_res
    mock_verifier.diagnose_failure.return_value = FailureDiagnosis(
        has_failures=True, failure_type="TEST_ASSERTION_FAILURE"
    )

    controller = SelfHealingController(verifier=mock_verifier, max_iterations=2)
    repair_fn = MagicMock()

    result = controller.run_healing_cycle("foo.py", "test_foo.py", repair_fn)
    assert result.success is False
    assert result.iterations_count == 2
    assert repair_fn.call_count == 1  # Called after iteration 1, exhausted at 2


def test_verification_tools_registered_in_tool_registry():
    tools = tool_registry.get_all_tools()
    assert "verify_code_syntax" in tools
    assert "run_code_tests" in tools
    assert "diagnose_test_failure" in tools


def test_verify_code_syntax_tool_invocation():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write("def hello():\n    return 'world'\n")
        path = f.name
    try:
        res = verify_code_syntax(path)
        assert "Syntax Valid" in res
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_verify_code_syntax_tool_missing_file():
    res = verify_code_syntax("non_existent_xyz.py")
    assert "Error: File does not exist" in res


def test_diagnose_test_failure_tool_invocation():
    res = diagnose_test_failure("FAILED test_math.py::test_add - AssertionError")
    assert "AUTOMATED TEST-DRIVEN REPAIR DIAGNOSTIC" in res


def test_coder_agent_has_verification_tools():
    coder_cap = registry.get_capabilities("coder")
    assert coder_cap is not None
    assert "verify_code_syntax" in coder_cap.tools
    assert "run_code_tests" in coder_cap.tools


def test_qa_tester_agent_has_verification_tools():
    qa_cap = registry.get_capabilities("qa_tester")
    assert qa_cap is not None
    assert "verify_code_syntax" in qa_cap.tools
    assert "run_code_tests" in qa_cap.tools
    assert "diagnose_test_failure" in qa_cap.tools
