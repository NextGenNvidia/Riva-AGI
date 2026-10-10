"""Unit tests for system_software.hardware modules."""

import pytest
from system_software.hardware.cpu import get_cpu_info
from system_software.hardware.memory import get_memory_info
from system_software.hardware.disk import get_disk_info
from system_software.hardware.battery import get_battery_info
from system_software.hardware.network import get_network_info


def test_get_cpu_info():
    info = get_cpu_info(interval=0.01)
    assert isinstance(info, dict)
    assert "usage_percent" in info
    assert "physical_cores" in info
    assert "total_cores" in info
    assert info["total_cores"] >= 1
    assert 0.0 <= info["usage_percent"] <= 100.0


def test_get_memory_info():
    info = get_memory_info()
    assert isinstance(info, dict)
    assert "percent" in info
    assert "total_gb" in info
    assert "used_gb" in info
    assert "available_gb" in info
    assert 0.0 <= info["percent"] <= 100.0
    assert info["total_gb"] >= 0.0
    assert "swap" in info


def test_get_disk_info():
    info = get_disk_info()
    assert isinstance(info, dict)
    assert "primary_used_percent" in info
    assert "partitions" in info
    assert isinstance(info["partitions"], list)
    assert len(info["partitions"]) >= 1
    p = info["partitions"][0]
    assert "mountpoint" in p
    assert "total_gb" in p
    assert "used_gb" in p
    assert "percent" in p


def test_get_battery_info():
    info = get_battery_info()
    assert isinstance(info, dict)
    assert "has_battery" in info
    assert "percent" in info
    assert "plugged_in" in info
    assert 0.0 <= info["percent"] <= 100.0


def test_get_network_info():
    info = get_network_info()
    assert isinstance(info, dict)
    assert "interfaces" in info
    assert "io_stats" in info
    assert isinstance(info["interfaces"], list)
    assert "bytes_sent_mb" in info["io_stats"]
