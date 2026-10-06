"""
Unit Tests for Self-Healing & Transactional Auto-Rollback Gate (Pillar 9)
"""

import os
import pytest
from orchestration.orchestrator.security import (
    WorkspaceTransactionManager,
    SecurityGate,
)


def test_transaction_manager_existing_file_rollback(tmp_path):
    test_file = tmp_path / "sample.py"
    test_file.write_text("def hello(): return 1\n", encoding="utf-8")

    mgr = WorkspaceTransactionManager()
    mgr.record_pre_state(str(test_file))

    # Simulate bad agent mutation
    test_file.write_text("def broken syntax (:(\n", encoding="utf-8")
    assert "broken" in test_file.read_text(encoding="utf-8")

    # Trigger Rollback
    restored = mgr.rollback()
    assert len(restored) == 1
    assert "Restored modified file" in restored[0]
    assert test_file.read_text(encoding="utf-8") == "def hello(): return 1\n"


def test_transaction_manager_new_file_rollback(tmp_path):
    new_file = tmp_path / "corrupted_scaffold.py"

    mgr = WorkspaceTransactionManager()
    mgr.record_pre_state(str(new_file))

    # Simulate agent creating file
    new_file.write_text("bad code", encoding="utf-8")
    assert new_file.exists()

    # Trigger Rollback
    restored = mgr.rollback()
    assert len(restored) == 1
    assert "Deleted new file" in restored[0]
    assert not new_file.exists()


def test_transaction_commit(tmp_path):
    valid_file = tmp_path / "clean.py"
    valid_file.write_text("initial", encoding="utf-8")

    mgr = WorkspaceTransactionManager()
    mgr.record_pre_state(str(valid_file))

    valid_file.write_text("clean update", encoding="utf-8")
    mgr.commit()

    assert mgr.pending_count == 0
    # Changes persist
    assert valid_file.read_text(encoding="utf-8") == "clean update"


def test_security_gate_integration():
    gate = SecurityGate()
    target_path = os.path.join(os.getcwd(), "scratch", "gate_test.py")
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write("original")

    try:
        # Evaluate tool call triggers pre-state recording
        allowed, msg = gate.evaluate_tool_call(
            tool_name="write_file",
            args={"file_path": target_path},
            caller_agent="coder"
        )
        assert allowed
        assert gate.transaction_mgr.pending_count == 1

        # Mutate and rollback via gate helper
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("mutation")
        restored = gate.rollback_workspace()
        assert len(restored) == 1
        with open(target_path, "r", encoding="utf-8") as f:
            assert f.read() == "original"
    finally:
        if os.path.exists(target_path):
            os.remove(target_path)
