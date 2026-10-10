"""Process management and resource inspection for Riva-AGI."""

from typing import Any, Dict, List, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def list_top_processes(
    limit: int = 5,
    sort_by: str = "memory",
) -> List[Dict[str, Any]]:
    """
    Returns the top resource-consuming processes running on the system.
    
    Args:
        limit: Number of processes to return (default 5).
        sort_by: 'memory' (sort by RSS memory) or 'cpu' (sort by CPU %).
    
    Returns:
        List of dicts with PID, name, CPU %, memory %, and status.
    """
    if not HAS_PSUTIL:
        return []

    processes = []
    for proc in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            processes.append({
                "pid": info["pid"],
                "name": info["name"] or "unknown",
                "cpu_percent": round(info["cpu_percent"] or 0.0, 1),
                "memory_percent": round(info["memory_percent"] or 0.0, 1),
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    key = "memory_percent" if sort_by == "memory" else "cpu_percent"
    processes.sort(key=lambda x: x.get(key, 0.0), reverse=True)
    return processes[:limit]


def get_process_details(pid: int) -> Optional[Dict[str, Any]]:
    """
    Fetches detailed operational metadata for a specific PID.
    
    Args:
        pid: Process ID.
    
    Returns:
        Detailed dictionary or None if process is not found.
    """
    if not HAS_PSUTIL:
        return None

    try:
        proc = psutil.Process(pid)
        mem_info = proc.memory_info()
        return {
            "pid": proc.pid,
            "name": proc.name(),
            "status": proc.status(),
            "cpu_percent": round(proc.cpu_percent(interval=0.05), 1),
            "memory_percent": round(proc.memory_percent(), 1),
            "rss_mb": round(mem_info.rss / (1024 ** 2), 2),
            "vms_mb": round(mem_info.vms / (1024 ** 2), 2),
            "num_threads": proc.num_threads(),
            "create_time": proc.create_time(),
            "cmdline": proc.cmdline()[:5] if proc.cmdline() else [],
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None
