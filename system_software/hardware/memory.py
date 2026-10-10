"""RAM and Virtual Memory telemetry for Riva-AGI."""

from typing import Any, Dict

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_memory_info() -> Dict[str, Any]:
    """
    Returns system RAM and swap memory statistics.
    
    Returns:
        Dict containing total, used, available, free, and percentage memory usage.
    """
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "percent": float(mem.percent),
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "used_gb": round(mem.used / (1024 ** 3), 2),
            "available_gb": round(mem.available / (1024 ** 3), 2),
            "free_gb": round(mem.free / (1024 ** 3), 2),
            "swap": {
                "total_gb": round(swap.total / (1024 ** 3), 2),
                "used_gb": round(swap.used / (1024 ** 3), 2),
                "free_gb": round(swap.free / (1024 ** 3), 2),
                "percent": float(swap.percent),
            },
        }

    # Zero-dependency fallback
    return {
        "percent": 0.0,
        "total_gb": 0.0,
        "used_gb": 0.0,
        "available_gb": 0.0,
        "free_gb": 0.0,
        "swap": {
            "total_gb": 0.0,
            "used_gb": 0.0,
            "free_gb": 0.0,
            "percent": 0.0,
        },
    }
