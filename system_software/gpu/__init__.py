"""GPU telemetry package for Riva-AGI."""

from system_software.gpu.nvidia import get_gpu_info, is_nvidia_smi_available
from system_software.gpu.mock import get_mock_gpu_info

__all__ = [
    "get_gpu_info",
    "is_nvidia_smi_available",
    "get_mock_gpu_info",
]
