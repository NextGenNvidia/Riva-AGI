"""
System Monitor Module for Riva-AGI
Monitors CPU, RAM, Battery, and NVIDIA GPU metrics with dynamic CLI progress bars.
Compatible with Python 3.12+ & 3.13.
"""

import shutil
import subprocess
from typing import Any, Dict, List, Optional
import psutil

# Terminal Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def create_progress_bar(percent: float, length: int = 24, reverse_colors: bool = False) -> str:
    """
    Renders a visual progress bar like: [██████░░░░░░░░░░░░] 25.0%
    - reverse_colors: If True, high is good (e.g. Battery: Green > 50%, Red < 20%)
                      If False, low is good (e.g. CPU/GPU: Green < 60%, Red > 85%)
    """
    pct = max(0.0, min(100.0, float(percent)))
    filled_len = int(round(length * (pct / 100.0)))
    empty_len = length - filled_len

    bar = "█" * filled_len + "░" * empty_len

    # Determine status color
    if reverse_colors:
        color = GREEN if pct >= 50 else (YELLOW if pct >= 20 else RED)
    else:
        color = GREEN if pct < 60 else (YELLOW if pct < 85 else RED)

    return f"[{color}{bar}{RESET}] {color}{pct:5.1f}%{RESET}"


def get_cpu_info() -> Dict[str, Any]:
    """Returns CPU usage percentage and core counts."""
    return {
        "usage_percent": psutil.cpu_percent(interval=1),
        "physical_cores": psutil.cpu_count(logical=False),
        "total_cores": psutil.cpu_count(logical=True),
    }


def get_memory_info() -> Dict[str, Any]:
    """Returns system RAM usage."""
    mem = psutil.virtual_memory()
    return {
        "percent": mem.percent,
        "used_gb": round(mem.used / (1024 ** 3), 1),
        "total_gb": round(mem.total / (1024 ** 3), 1),
    }


def get_battery_info() -> Dict[str, Any]:
    """Returns battery percentage, plugged-in status, and remaining time."""
    battery = psutil.sensors_battery()

    if battery is None:
        return {
            "has_battery": False,
            "status": "No battery detected (Desktop or unsupported hardware)",
        }

    seconds_left = battery.secsleft
    if (
        seconds_left == psutil.POWER_TIME_UNLIMITED
        or seconds_left == psutil.POWER_TIME_UNKNOWN
    ):
        time_remaining_str = "Calculating or Plugged In"
    else:
        hours = seconds_left // 3600
        minutes = (seconds_left % 3600) // 60
        time_remaining_str = f"{hours}h {minutes}m"

    return {
        "has_battery": True,
        "percent": round(battery.percent, 1),
        "plugged_in": battery.power_plugged,
        "time_remaining": time_remaining_str,
    }


def get_gpu_info() -> List[Dict[str, Any]]:
    """Returns details for available NVIDIA GPUs using nvidia-smi."""
    gpu_list = []

    if not shutil.which("nvidia-smi"):
        return [{"error": "nvidia-smi not found (No NVIDIA driver detected)"}]

    query_cmd = [
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]

    try:
        result = subprocess.run(
            query_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                idx, name, util, mem_used, mem_total, temp = parts[:6]
                mem_used_f = float(mem_used)
                mem_total_f = float(mem_total)
                mem_pct = round((mem_used_f / mem_total_f) * 100, 1) if mem_total_f else 0.0

                gpu_list.append({
                    "id": int(idx),
                    "name": name,
                    "load_percent": float(util),
                    "memory_used_mb": mem_used_f,
                    "memory_total_mb": mem_total_f,
                    "memory_percent": mem_pct,
                    "temperature_c": int(temp),
                })
    except Exception as e:
        gpu_list.append({"error": f"GPU detection failed: {e}"})

    if not gpu_list:
        return [{"error": "No dedicated NVIDIA GPU found"}]

    return gpu_list


def print_system_report() -> None:
    """Prints a styled, user-friendly system health report to terminal."""
    print(f"\n{BOLD}{CYAN}==================== SYSTEM MONITOR ===================={RESET}")

    # 1. CPU
    cpu = get_cpu_info()
    print(f"\n{BOLD}[CPU]{RESET}")
    print(f"  Usage: {create_progress_bar(cpu['usage_percent'])}")
    print(f"  Cores: {cpu['physical_cores']} Physical | {cpu['total_cores']} Logical")

    # 2. RAM
    mem = get_memory_info()
    print(f"\n{BOLD}[RAM / Memory]{RESET}")
    print(f"  Usage: {create_progress_bar(mem['percent'])}  ({mem['used_gb']} GB / {mem['total_gb']} GB)")

    # 3. Battery
    bat = get_battery_info()
    print(f"\n{BOLD}[Battery]{RESET}")
    if bat["has_battery"]:
        status = "Charging / Plugged in" if bat["plugged_in"] else "On Battery"
        print(f"  Level: {create_progress_bar(bat['percent'], reverse_colors=True)}  ({status})")
        print(f"  Time:  {bat['time_remaining']}")
    else:
        print(f"  {bat['status']}")

    # 4. GPU
    gpus = get_gpu_info()
    for g in gpus:
        if "error" in g:
            print(f"\n{BOLD}[GPU]{RESET}\n  {g['error']}")
        else:
            print(f"\n{BOLD}[GPU {g['id']}: {g['name']}]{RESET}")
            print(f"  Load:  {create_progress_bar(g['load_percent'])}")
            print(f"  VRAM:  {create_progress_bar(g['memory_percent'])}  ({int(g['memory_used_mb'])} MB / {int(g['memory_total_mb'])} MB)")
            print(f"  Temp:  {g['temperature_c']}°C")

    print(f"\n{BOLD}{CYAN}========================================================{RESET}\n")


if __name__ == "__main__":
    print_system_report()
