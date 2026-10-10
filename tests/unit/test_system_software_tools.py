"""Unit tests for System Software Agent Tools integration."""

import json
import pytest
from orchestration.tools import tool_registry
from orchestration.tools.builtin.system_software_tools import (
    get_system_telemetry,
    get_gpu_telemetry,
    get_top_processes,
)


def test_tools_registered_in_tool_registry():
    assert "get_system_telemetry" in tool_registry
    assert "get_gpu_telemetry" in tool_registry
    assert "get_top_processes" in tool_registry

    tool_def = tool_registry.get_tool_definition("get_system_telemetry")
    assert tool_def is not None
    assert tool_def.category == "system"


def test_get_system_telemetry():
    result_str = get_system_telemetry()
    assert isinstance(result_str, str)
    data = json.loads(result_str)
    assert "health" in data
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data


def test_get_gpu_telemetry():
    result_str = get_gpu_telemetry(mock_if_missing=True)
    assert isinstance(result_str, str)
    data = json.loads(result_str)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "name" in data[0]


def test_get_top_processes():
    result_str = get_top_processes(limit=2, sort_by="memory")
    assert isinstance(result_str, str)
    data = json.loads(result_str)
    assert isinstance(data, list)
    if data:
        assert "pid" in data[0]
        assert "memory_percent" in data[0]
