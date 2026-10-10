"""
Autonomous Self-Healing Controller for Riva-AGI Coding Loop.
============================================================
Manages the test-driven repair cycle: Executes tests, extracts diagnostic tracebacks,
generates targeted repair prompts, and iteratively invokes agents until all tests pass.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from orchestration.verification.verifier import (
    CodeVerifier,
    FailureDiagnosis,
    SyntaxVerificationResult,
    TestExecutionResult,
)

logger = logging.getLogger("orchestration.verification.self_healing")


@dataclass
class SelfHealingAttempt:
    """Records details of a single self-healing repair attempt."""
    iteration: int
    syntax_result: SyntaxVerificationResult
    test_result: Optional[TestExecutionResult] = None
    diagnosis: Optional[FailureDiagnosis] = None
    repair_prompt: str = ""
    repaired: bool = False


@dataclass
class SelfHealingResult:
    """Outcome of the complete autonomous self-healing cycle."""
    success: bool
    iterations_count: int
    max_iterations: int
    attempts: List[SelfHealingAttempt] = field(default_factory=list)
    final_summary: str = ""
    target_file: Optional[str] = None
    test_target: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "iterations_count": self.iterations_count,
            "max_iterations": self.max_iterations,
            "final_summary": self.final_summary,
            "target_file": self.target_file,
            "test_target": self.test_target,
            "attempt_count": len(self.attempts),
        }


class SelfHealingController:
    """Orchestrates autonomous code repair and verification loops."""

    def __init__(self, verifier: Optional[CodeVerifier] = None, max_iterations: int = 3):
        self.verifier = verifier or CodeVerifier()
        self.max_iterations = max(1, max_iterations)

    def run_healing_cycle(
        self,
        target_file: str,
        test_file: str,
        repair_fn: Callable[[str], str],
    ) -> SelfHealingResult:
        """Runs the iterative self-healing loop until tests pass or max iterations reached.

        Args:
            target_file: Path to source code file being repaired.
            test_file: Path to unit test file validating the code.
            repair_fn: Callback function (e.g. LLM agent invocation) that receives
                       the diagnostic repair prompt and applies a code fix.

        Returns:
            SelfHealingResult with full history of attempts, diagnostics, and final status.
        """
        attempts: List[SelfHealingAttempt] = []
        logger.info(
            f"Starting autonomous self-healing cycle for '{target_file}' against '{test_file}' "
            f"(max_iterations={self.max_iterations})"
        )

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Self-healing iteration {iteration}/{self.max_iterations}")

            # 1. Verify AST syntax of target file
            syntax_res = self.verifier.verify_syntax(target_file)
            if not syntax_res.valid:
                diag = FailureDiagnosis(
                    has_failures=True,
                    failure_type="SYNTAX_ERROR",
                    root_cause=syntax_res.to_summary(),
                    suggestion="Fix syntax errors, unclosed brackets, or invalid indentation.",
                )
                repair_prompt = diag.format_repair_prompt(target_file=target_file)
                attempt = SelfHealingAttempt(
                    iteration=iteration,
                    syntax_result=syntax_res,
                    diagnosis=diag,
                    repair_prompt=repair_prompt,
                    repaired=False,
                )
                attempts.append(attempt)

                if iteration < self.max_iterations:
                    logger.warning(f"Syntax error on iteration {iteration}. Requesting agent repair...")
                    repair_fn(repair_prompt)
                    continue
                else:
                    return SelfHealingResult(
                        success=False,
                        iterations_count=iteration,
                        max_iterations=self.max_iterations,
                        attempts=attempts,
                        final_summary=f"Failed: Syntax error persisted after {self.max_iterations} iterations.",
                        target_file=target_file,
                        test_target=test_file,
                    )

            # 2. Execute test suite
            test_res = self.verifier.run_tests(test_file)
            if test_res.passed:
                logger.info(f"Verification SUCCESS on iteration {iteration}! All tests passed.")
                attempt = SelfHealingAttempt(
                    iteration=iteration,
                    syntax_result=syntax_res,
                    test_result=test_res,
                    diagnosis=FailureDiagnosis(has_failures=False, failure_type="NONE"),
                    repaired=True,
                )
                attempts.append(attempt)
                return SelfHealingResult(
                    success=True,
                    iterations_count=iteration,
                    max_iterations=self.max_iterations,
                    attempts=attempts,
                    final_summary=f"Success: Tests passed on iteration {iteration} ({test_res.summary}).",
                    target_file=target_file,
                    test_target=test_file,
                )

            # 3. Tests failed - extract actionable diagnosis
            combined_output = f"{test_res.stdout}\n{test_res.stderr}"
            diagnosis = self.verifier.diagnose_failure(combined_output, exit_code=test_res.exit_code)
            repair_prompt = diagnosis.format_repair_prompt(target_file=target_file)

            attempt = SelfHealingAttempt(
                iteration=iteration,
                syntax_result=syntax_res,
                test_result=test_res,
                diagnosis=diagnosis,
                repair_prompt=repair_prompt,
                repaired=False,
            )
            attempts.append(attempt)

            if iteration < self.max_iterations:
                logger.info(
                    f"Iteration {iteration} failed with {diagnosis.failure_type}. "
                    f"Invoking agent with automated repair prompt..."
                )
                repair_fn(repair_prompt)
            else:
                logger.warning(f"Exhausted maximum iterations ({self.max_iterations}). Self-healing stopped.")

        return SelfHealingResult(
            success=False,
            iterations_count=self.max_iterations,
            max_iterations=self.max_iterations,
            attempts=attempts,
            final_summary=f"Failed: Tests still failing after {self.max_iterations} repair attempts.",
            target_file=target_file,
            test_target=test_file,
        )
