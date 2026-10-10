"""CPU telemetry and performance metrics for Riva-AGI."""

import os
import platform
from typing import Any, Dict, List, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _safe_get_processor_and_arch():
    """Safely retrieves CPU architecture and processor string without crashing on Windows WMI."""
    arch = os.environ.get("PROCESSOR_ARCHITECTURE")
    processor = os.environ.get("PROCESSOR_IDENTIFIER")
    if not arch:
        try:
            arch = platform.machine()
        except Exception:
            arch = "unknown"
    if not processor:
        try:
            processor = platform.processor() or arch
        except Exception:
            processor = arch or "unknown"
    return processor or "Unknown Processor", arch or "x86_64"


def get_cpu_info(interval: Optional[float] = 0.05) -> Dict[str, Any]:
    """
    Collects detailed CPU topology, architecture, and current utilization.
    
    Args:
        interval: Sampling interval for CPU measurement (seconds).
    
    Returns:
        Dict containing CPU model, architecture, cores, usage %, and per-cpu metrics.
    """
    processor_str, arch_str = _safe_get_processor_and_arch()

    if HAS_PSUTIL:
        usage_percent = float(psutil.cpu_percent(interval=interval))
        per_cpu = [float(x) for x in psutil.cpu_percent(interval=None, percpu=True)]
        physical_cores = psutil.cpu_count(logical=False) or 1
        total_cores = psutil.cpu_count(logical=True) or 1
        
        try:
            freq = psutil.cpu_freq()
            current_freq_mhz = round(freq.current, 1) if freq else None
            min_freq_mhz = round(freq.min, 1) if freq and freq.min else None
            max_freq_mhz = round(freq.max, 1) if freq and freq.max else None
        except Exception:
            current_freq_mhz = None
            min_freq_mhz = None
            max_freq_mhz = None
    else:
        # Fallback to standard library
        total_cores = os.cpu_count() or 1
        physical_cores = max(1, total_cores // 2)
        usage_percent = 0.0
        per_cpu = []
        current_freq_mhz = None
        min_freq_mhz = None
        max_freq_mhz = None

    return {
        "architecture": arch_str,
        "processor": processor_str,
        "physical_cores": physical_cores,
        "total_cores": total_cores,
        "usage_percent": usage_percent,
        "per_cpu_percent": per_cpu,
        "frequency_mhz": {
            "current": current_freq_mhz,
            "min": min_freq_mhz,
            "max": max_freq_mhz,
        },
    }
