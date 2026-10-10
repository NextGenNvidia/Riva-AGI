"""
System Monitor Compatibility Shim for Riva-AGI
==============================================
Provides full backward compatibility with Backend/services/system_service.py (PR #54)
and legacy scripts by delegating directly to the modular system_software package (Track 4).
"""

from system_software import (
    get_cpu_info,
    get_memory_info,
    get_battery_info,
    get_gpu_info,
    print_system_report,
)
from system_software.cli import create_progress_bar

__all__ = [
    "get_cpu_info",
    "get_memory_info",
    "get_battery_info",
    "get_gpu_info",
    "print_system_report",
    "create_progress_bar",
]

if __name__ == "__main__":
    print_system_report()
