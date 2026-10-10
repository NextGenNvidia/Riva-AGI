"""
Riva-AGI System Software Subsystem (Track 4)
============================================
Comprehensive hardware telemetry, NVIDIA GPU monitoring, OS resource inspection,
and health assessment for the Riva-AGI autonomous agent framework.
"""

from system_software.config import config, SystemSoftwareConfig
from system_software.hardware.cpu import get_cpu_info
from system_software.hardware.memory import get_memory_info
from system_software.hardware.disk import get_disk_info
from system_software.hardware.battery import get_battery_info
from system_software.hardware.network import get_network_info
from system_software.gpu.nvidia import get_gpu_info, is_nvidia_smi_available
from system_software.gpu.mock import get_mock_gpu_info
from system_software.process.manager import list_top_processes, get_process_details
from system_software.service import SystemSoftwareService, system_service
from system_software.cli import print_system_report

__version__ = "1.0.0"

__all__ = [
    "config",
    "SystemSoftwareConfig",
    "get_cpu_info",
    "get_memory_info",
    "get_disk_info",
    "get_battery_info",
    "get_network_info",
    "get_gpu_info",
    "is_nvidia_smi_available",
    "get_mock_gpu_info",
    "list_top_processes",
    "get_process_details",
    "SystemSoftwareService",
    "system_service",
    "print_system_report",
    "__version__",
]
