"""Unit tests for system_software.process module."""

import os
import pytest
from system_software.process.manager import list_top_processes, get_process_details


def test_list_top_processes():
    procs = list_top_processes(limit=3, sort_by="memory")
    assert isinstance(procs, list)
    if procs:
        assert len(procs) <= 3
        p = procs[0]
        assert "pid" in p
        assert "name" in p
        assert "memory_percent" in p
        assert "cpu_percent" in p


def test_get_process_details_current_process():
    current_pid = os.getpid()
    details = get_process_details(current_pid)
    assert details is not None
    assert details["pid"] == current_pid
    assert "name" in details
    assert "status" in details
    assert "rss_mb" in details


def test_get_process_details_nonexistent_pid():
    details = get_process_details(9999999)
    assert details is None
