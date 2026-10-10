"""Unit tests for the root system_monitor.py backward compatibility shim."""

import system_monitor


def test_system_monitor_exports():
    cpu = system_monitor.get_cpu_info()
    assert isinstance(cpu, dict)
    assert "usage_percent" in cpu

    mem = system_monitor.get_memory_info()
    assert isinstance(mem, dict)
    assert "percent" in mem

    bat = system_monitor.get_battery_info()
    assert isinstance(bat, dict)
    assert "has_battery" in bat

    gpu = system_monitor.get_gpu_info()
    assert isinstance(gpu, list)
    assert len(gpu) >= 1
