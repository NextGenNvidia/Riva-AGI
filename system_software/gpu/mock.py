"""Mock NVIDIA GPU telemetry for testing and development environments."""

from typing import Any, Dict, List


def get_mock_gpu_info() -> List[Dict[str, Any]]:
    """
    Returns realistic simulated NVIDIA GPU metrics (e.g. NVIDIA A100-SXM4-80GB).
    Used for unit testing and running on machines without dedicated GPUs.
    """
    return [
        {
            "id": 0,
            "has_gpu": True,
            "name": "NVIDIA A100-SXM4-80GB (Simulated)",
            "load_percent": 34.5,
            "memory_used_mb": 24576.0,
            "memory_total_mb": 81920.0,
            "memory_free_mb": 57344.0,
            "memory_percent": 30.0,
            "temperature_c": 52,
            "power_draw_w": 185.0,
            "driver_version": "550.54.14",
        }
    ]
