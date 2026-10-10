"""Unit tests for SystemSoftwareService and health evaluation."""

import pytest
from system_software.service import SystemSoftwareService, system_service
from system_software.config import SystemSoftwareConfig


def test_evaluate_health_healthy():
    svc = SystemSoftwareService()
    cpu = {"usage_percent": 25.0}
    mem = {"percent": 45.0}
    disk = {"primary_used_percent": 50.0}
    gpu = [{"has_gpu": True, "name": "GPU", "memory_percent": 30.0, "temperature_c": 50}]

    health = svc.evaluate_health(cpu, mem, disk, gpu)
    assert health["status"] == "HEALTHY"
    assert len(health["alerts"]) == 0


def test_evaluate_health_warning():
    custom_cfg = SystemSoftwareConfig(CPU_WARNING_THRESHOLD=70.0, CPU_CRITICAL_THRESHOLD=90.0)
    svc = SystemSoftwareService(sys_config=custom_cfg)
    cpu = {"usage_percent": 75.0}
    mem = {"percent": 40.0}
    disk = {"primary_used_percent": 50.0}
    gpu = []

    health = svc.evaluate_health(cpu, mem, disk, gpu)
    assert health["status"] == "WARNING"
    assert len(health["alerts"]) == 1
    assert "WARNING: CPU" in health["alerts"][0]


def test_evaluate_health_critical():
    custom_cfg = SystemSoftwareConfig(MEMORY_CRITICAL_THRESHOLD=90.0)
    svc = SystemSoftwareService(sys_config=custom_cfg)
    cpu = {"usage_percent": 20.0}
    mem = {"percent": 95.0}
    disk = {"primary_used_percent": 50.0}
    gpu = []

    health = svc.evaluate_health(cpu, mem, disk, gpu)
    assert health["status"] == "CRITICAL"
    assert len(health["alerts"]) == 1
    assert "CRITICAL: RAM" in health["alerts"][0]


def test_get_system_snapshot():
    snapshot = system_service.get_system_snapshot()
    assert isinstance(snapshot, dict)
    assert "health" in snapshot
    assert "cpu" in snapshot
    assert "memory" in snapshot
    assert "disk" in snapshot
    assert "gpu" in snapshot
    assert "top_processes" in snapshot


@pytest.mark.anyio
async def test_get_system_snapshot_async():
    snapshot = await system_service.get_system_snapshot_async()
    assert isinstance(snapshot, dict)
    assert "health" in snapshot
    assert snapshot["health"]["status"] in ("HEALTHY", "WARNING", "CRITICAL")
