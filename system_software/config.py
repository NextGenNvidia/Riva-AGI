"""Configuration for the Riva-AGI System Software & Telemetry Subsystem."""

import os
from dataclasses import dataclass


@dataclass
class SystemSoftwareConfig:
    """System Software threshold and polling configuration."""

    # Resource alert thresholds (%)
    CPU_WARNING_THRESHOLD: float = float(os.getenv("SYS_CPU_WARNING_THRESHOLD", "75.0"))
    CPU_CRITICAL_THRESHOLD: float = float(os.getenv("SYS_CPU_CRITICAL_THRESHOLD", "90.0"))

    MEMORY_WARNING_THRESHOLD: float = float(os.getenv("SYS_MEMORY_WARNING_THRESHOLD", "80.0"))
    MEMORY_CRITICAL_THRESHOLD: float = float(os.getenv("SYS_MEMORY_CRITICAL_THRESHOLD", "95.0"))

    DISK_WARNING_THRESHOLD: float = float(os.getenv("SYS_DISK_WARNING_THRESHOLD", "85.0"))
    DISK_CRITICAL_THRESHOLD: float = float(os.getenv("SYS_DISK_CRITICAL_THRESHOLD", "95.0"))

    GPU_VRAM_WARNING_THRESHOLD: float = float(os.getenv("SYS_GPU_VRAM_WARNING_THRESHOLD", "80.0"))
    GPU_VRAM_CRITICAL_THRESHOLD: float = float(os.getenv("SYS_GPU_VRAM_CRITICAL_THRESHOLD", "95.0"))

    GPU_TEMP_WARNING_THRESHOLD: float = float(os.getenv("SYS_GPU_TEMP_WARNING_THRESHOLD", "80.0"))
    GPU_TEMP_CRITICAL_THRESHOLD: float = float(os.getenv("SYS_GPU_TEMP_CRITICAL_THRESHOLD", "90.0"))

    # Mock mode (useful in development or non-GPU CI environments)
    MOCK_GPU_ENABLED: bool = os.getenv("MOCK_NVIDIA_GPU", "false").lower() in ("true", "1", "yes")

    # Sampling interval in seconds
    CPU_SAMPLE_INTERVAL: float = float(os.getenv("SYS_CPU_SAMPLE_INTERVAL", "0.5"))


config = SystemSoftwareConfig()
