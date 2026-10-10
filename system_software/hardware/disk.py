"""Storage partitions and disk I/O metrics for Riva-AGI."""

import os
import shutil
from typing import Any, Dict, List

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_disk_info() -> Dict[str, Any]:
    """
    Returns filesystem partitions, storage capacity, free space, and I/O counters.
    
    Returns:
        Dict containing partition details and aggregate storage metrics.
    """
    partitions: List[Dict[str, Any]] = []
    
    if HAS_PSUTIL:
        for p in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(p.mountpoint)
                partitions.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent": float(usage.percent),
                })
            except (PermissionError, OSError):
                continue
                
        io_counters = psutil.disk_io_counters()
        io_stats = {
            "read_bytes_mb": round(io_counters.read_bytes / (1024 ** 2), 2) if io_counters else 0.0,
            "write_bytes_mb": round(io_counters.write_bytes / (1024 ** 2), 2) if io_counters else 0.0,
            "read_count": io_counters.read_count if io_counters else 0,
            "write_count": io_counters.write_count if io_counters else 0,
        }
    else:
        # Fallback using shutil
        root_path = os.path.abspath(os.sep)
        usage = shutil.disk_usage(root_path)
        partitions.append({
            "device": root_path,
            "mountpoint": root_path,
            "fstype": "unknown",
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
        })
        io_stats = {"read_bytes_mb": 0.0, "write_bytes_mb": 0.0, "read_count": 0, "write_count": 0}

    primary_partition = partitions[0] if partitions else {
        "device": "N/A", "mountpoint": "/", "fstype": "N/A",
        "total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "percent": 0.0
    }

    return {
        "primary_used_percent": primary_partition["percent"],
        "partitions": partitions,
        "io_stats": io_stats,
    }
