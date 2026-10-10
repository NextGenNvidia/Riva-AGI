"""
System Software & Hardware Telemetry Agent Tools for Riva-AGI.
Exposes Track 4 hardware observability and NVIDIA GPU inspection to autonomous agents.
"""

import json
from typing import Optional
from orchestration.tools.registry import tool
from system_software import (
    system_service,
    get_cpu_info,
    get_memory_info,
    get_gpu_info,
    list_top_processes,
)


@tool(category="system")
def get_system_telemetry() -> str:
    """Collects real-time hardware telemetry across CPU, RAM, Disk, Battery, and overall health status.

    Returns:
        JSON string containing hardware metrics, active alert thresholds, and health verdict.
    """
    snapshot = system_service.get_system_snapshot()
    return json.dumps(snapshot, indent=2)


@tool(category="system")
def get_gpu_telemetry(mock_if_missing: bool = False) -> str:
    """Inspects NVIDIA GPU compute utilization, VRAM usage, temperature, and power draw.

    Args:
        mock_if_missing: If True, returns simulated NVIDIA A100 metrics if no physical GPU exists.

    Returns:
        JSON string containing GPU specifications, VRAM percent, load percent, and temperature.
    """
    gpus = get_gpu_info(force_mock=mock_if_missing)
    return json.dumps(gpus, indent=2)


@tool(category="system")
def get_top_processes(limit: int = 5, sort_by: str = "memory") -> str:
    """Lists the top resource-consuming OS processes currently running on the host system.

    Args:
        limit: Number of top processes to return (default: 5).
        sort_by: Metric to sort by: 'memory' (default) or 'cpu'.

    Returns:
        JSON string listing process PIDs, names, CPU %, and memory % consumption.
    """
    procs = list_top_processes(limit=limit, sort_by=sort_by)
    return json.dumps(procs, indent=2)
