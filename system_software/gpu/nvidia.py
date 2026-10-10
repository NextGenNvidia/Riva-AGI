"""NVIDIA GPU Telemetry and NVML parsing for Riva-AGI."""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from system_software.config import config


def is_nvidia_smi_available() -> bool:
    """Checks whether the nvidia-smi executable exists on the system PATH."""
    return shutil.which("nvidia-smi") is not None


def get_gpu_info(force_mock: Optional[bool] = None) -> List[Dict[str, Any]]:
    """
    Collects detailed metrics from NVIDIA GPUs using nvidia-smi.
    
    If nvidia-smi is not found and mock is enabled (via config or parameter),
    returns simulated metrics suitable for non-GPU development and testing.
    
    Returns:
        List of dictionaries with GPU telemetry (index, name, compute load, VRAM, temp, power).
    """
    should_mock = force_mock if force_mock is not None else config.MOCK_GPU_ENABLED

    if not is_nvidia_smi_available():
        if should_mock:
            from system_software.gpu.mock import get_mock_gpu_info
            return get_mock_gpu_info()
        return [{
            "id": 0,
            "has_gpu": False,
            "name": "No Dedicated NVIDIA GPU",
            "error": "nvidia-smi not found in PATH (No NVIDIA driver detected)",
            "load_percent": 0.0,
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "memory_free_mb": 0.0,
            "memory_percent": 0.0,
            "temperature_c": 0,
            "power_draw_w": 0.0,
            "driver_version": "N/A",
        }]

    query_cmd = [
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,memory.free,temperature.gpu,power.draw,driver_version",
        "--format=csv,noheader,nounits",
    ]

    gpu_list: List[Dict[str, Any]] = []

    try:
        proc = subprocess.run(
            query_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=5.0,
        )

        for line in proc.stdout.strip().splitlines():
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 9:
                idx, name, util, mem_used, mem_total, mem_free, temp, power, driver = parts[:9]
                
                try:
                    mem_used_f = float(mem_used)
                    mem_total_f = float(mem_total)
                    mem_free_f = float(mem_free)
                    mem_pct = round((mem_used_f / mem_total_f) * 100, 1) if mem_total_f > 0 else 0.0
                    util_f = float(util)
                    temp_i = int(temp)
                    power_f = float(power) if power != "[N/A]" else 0.0
                except (ValueError, TypeError):
                    continue

                gpu_list.append({
                    "id": int(idx),
                    "has_gpu": True,
                    "name": name,
                    "load_percent": util_f,
                    "memory_used_mb": mem_used_f,
                    "memory_total_mb": mem_total_f,
                    "memory_free_mb": mem_free_f,
                    "memory_percent": mem_pct,
                    "temperature_c": temp_i,
                    "power_draw_w": power_f,
                    "driver_version": driver,
                })
    except subprocess.TimeoutExpired:
        gpu_list.append({
            "id": 0,
            "has_gpu": False,
            "name": "NVIDIA GPU Timeout",
            "error": "Query to nvidia-smi timed out after 5 seconds",
            "load_percent": 0.0,
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "memory_free_mb": 0.0,
            "memory_percent": 0.0,
            "temperature_c": 0,
            "power_draw_w": 0.0,
            "driver_version": "N/A",
        })
    except Exception as exc:
        gpu_list.append({
            "id": 0,
            "has_gpu": False,
            "name": "NVIDIA GPU Detection Error",
            "error": f"Failed to query GPU telemetry: {exc}",
            "load_percent": 0.0,
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "memory_free_mb": 0.0,
            "memory_percent": 0.0,
            "temperature_c": 0,
            "power_draw_w": 0.0,
            "driver_version": "N/A",
        })

    if not gpu_list:
        if should_mock:
            from system_software.gpu.mock import get_mock_gpu_info
            return get_mock_gpu_info()
        return [{
            "id": 0,
            "has_gpu": False,
            "name": "No Dedicated NVIDIA GPU Found",
            "error": "nvidia-smi returned empty results",
            "load_percent": 0.0,
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "memory_free_mb": 0.0,
            "memory_percent": 0.0,
            "temperature_c": 0,
            "power_draw_w": 0.0,
            "driver_version": "N/A",
        }]

    return gpu_list
