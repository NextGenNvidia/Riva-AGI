"""
Riva-AGI Autonomous Self-Healing Coding & Verification Demo
===========================================================
Demonstrates the end-to-end autonomous test-driven repair cycle:
1. Static AST syntax validation.
2. Isolated subprocess pytest execution.
3. Automated traceback & assertion diagnosis.
4. Autonomous iterative repair loop (Coder -> Verifier -> Repair -> Pass).

Usage:
    python examples/demo_self_healing_coder.py
"""

import os
import sys
import tempfile
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestration.tools.registry import tool_registry
import orchestration.tools.builtin
from orchestration.orchestrator.registry import registry
import orchestration.agents.coder
import orchestration.agents.qa_tester
from orchestration.verification.verifier import CodeVerifier
from orchestration.verification.self_healing import SelfHealingController


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def demo_agent_tool_capabilities():
    print_header("1. Verification Tools Registered for Coder & QA Agents")
    all_tools = tool_registry.get_all_tools()
    verification_tools = [name for name in all_tools if any(k in name for k in ["verify", "test", "diagnose"])]
    print(f"Total tools in Riva-AGI registry: {len(all_tools)}")
    print("Verification tools available:")
    for name in verification_tools:
        desc = (tool_registry.get(name).description or "").split("\n")[0]
        print(f"  - {name:24} -> {desc}")

    print("\nCoder Agent Equipped Tools:")
    coder_cap = registry.get_capabilities("coder")
    for t in coder_cap.tools:
        is_ver = any(k in t for k in ["verify", "test", "diagnose"])
        tag = "[VERIFICATION TOOL]" if is_ver else "[CORE TOOL]"
        print(f"  - {t:24} {tag}")


def demo_ast_syntax_verification():
    print_header("2. Static AST Syntax Verification")
    valid_code = "def fibonacci(n: int) -> int:\n    return n if n <= 1 else fibonacci(n - 1) + fibonacci(n - 2)\n"
    invalid_code = "def fibonacci(n: int) -> int\n    return n if n <= 1 else fibonacci(n - 1) + fibonacci(n - 2)\n"

    print("Checking valid Python syntax:")
    res_valid = CodeVerifier.verify_syntax(valid_code)
    print(f"  Result: {res_valid.to_summary()}")

    print("\nChecking invalid Python syntax (missing colon at def):")
    res_invalid = CodeVerifier.verify_syntax(invalid_code)
    print(f"  Result: {res_invalid.to_summary()}")


def demo_failure_diagnosis():
    print_header("3. Automated Test Failure Diagnosis & Prompt Generation")
    sample_pytest_output = """
============================= test session starts =============================
tests/unit/test_discount.py::test_calculate_discount FAILED             [100%]

================================== FAILURES ===================================
___________________________ test_calculate_discount ___________________________

    def test_calculate_discount():
>       assert calculate_discount(100.0, 0.20) == 80.0
E       AssertionError: assert 120.0 == 80.0
E         +  where 120.0 = calculate_discount(100.0, 0.20)

tests/unit/test_discount.py:5: AssertionError
=========================== short test summary info ===========================
FAILED tests/unit/test_discount.py::test_calculate_discount - AssertionError: assert 120.0 == 80.0
============================== 1 failed in 0.08s ===============================
"""
    diagnosis = CodeVerifier.diagnose_failure(sample_pytest_output, exit_code=1)
    print(f"Detected Failure Type: {diagnosis.failure_type}")
    print(f"Failed Tests: {diagnosis.failed_tests}")
    print(f"Extracted Root Cause: {diagnosis.root_cause}")
    print("\nGenerated Actionable Repair Prompt:")
    print("-" * 50)
    print(diagnosis.format_repair_prompt(target_file="pricing/discount.py"))
    print("-" * 50)


def demo_autonomous_self_healing_loop():
    print_header("4. Live Autonomous Self-Healing Repair Cycle")

    with tempfile.TemporaryDirectory() as tmp_dir:
        code_file = os.path.join(tmp_dir, "calculator.py")
        test_file = os.path.join(tmp_dir, "test_calculator.py")

        # Create unit test file
        test_code = """
import pytest
from calculator import calculate_tax

def test_tax_standard():
    assert calculate_tax(100.0, 0.10) == 10.0

def test_tax_zero():
    assert calculate_tax(50.0, 0.0) == 0.0
"""
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        # Initial implementation with an intentional bug (multiplies price by 2 + rate)
        buggy_code = """
def calculate_tax(price: float, rate: float) -> float:
    # BUG: mistakenly multiplies price by 2
    return (price * 2) * rate
"""
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(buggy_code)

        print(f"Initial Code written to {os.path.basename(code_file)} (has deliberate calculation bug).")

        # Simulated autonomous repair callback (acts as coder agent receiving diagnostic prompt)
        def autonomous_coder_repair(diagnostic_prompt: str) -> str:
            print(f"\n[Agent Triggered] Coder received diagnostic feedback:\n  -> Failure: {diagnostic_prompt.splitlines()[1]}")
            print("  -> Diagnosing bug: Tax was calculated on 2 * price.")
            print("  -> Applying code patch to calculator.py...")

            fixed_code = """
def calculate_tax(price: float, rate: float) -> float:
    # PATCHED: correctly computes price * rate
    return price * rate
"""
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(fixed_code)
            return "Patched calculator.py with corrected formula."

        # Run Self-Healing Controller
        controller = SelfHealingController(max_iterations=3)
        result = controller.run_healing_cycle(
            target_file=code_file,
            test_file=test_file,
            repair_fn=autonomous_coder_repair,
        )

        print(f"\nSelf-Healing Cycle Final Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Iterations Required: {result.iterations_count}/{result.max_iterations}")
        print(f"Summary: {result.final_summary}")


def main():
    print("\n" + "#" * 65)
    print("   RIVA-AGI AUTONOMOUS SELF-HEALING CODING ENGINE DEMO")
    print("#" * 65)

    demo_agent_tool_capabilities()
    demo_ast_syntax_verification()
    demo_failure_diagnosis()
    demo_autonomous_self_healing_loop()

    print("\n" + "=" * 65)
    print("  Self-healing coding demonstration completed successfully!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
