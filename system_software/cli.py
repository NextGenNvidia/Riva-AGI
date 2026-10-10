"""Interactive CLI Dashboard for the Riva-AGI System Software Subsystem."""

import argparse
import json
import sys
import time
from typing import Any, Dict

from system_software.service import system_service
from system_software.hardware.cpu import get_cpu_info
from system_software.hardware.memory import get_memory_info
from system_software.hardware.disk import get_disk_info
from system_software.hardware.battery import get_battery_info
from system_software.hardware.network import get_network_info
from system_software.gpu.nvidia import get_gpu_info
from system_software.process.manager import list_top_processes

# Reconfigure stdout to UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI styling
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def create_progress_bar(percent: float, length: int = 24, reverse_colors: bool = False) -> str:
    """
    Renders a colorized progress bar with graceful character encoding support.
    """
    pct = max(0.0, min(100.0, float(percent)))
    filled_len = int(round(length * (pct / 100.0)))
    empty_len = length - filled_len

    # Detect if terminal encoding supports full unicode blocks
    encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    if "1252" in encoding.lower() or "ascii" in encoding.lower():
        fill_char = "#"
        empty_char = "-"
    else:
        fill_char = "█"
        empty_char = "░"

    bar = fill_char * filled_len + empty_char * empty_len

    if reverse_colors:
        color = GREEN if pct >= 50 else (YELLOW if pct >= 20 else RED)
    else:
        color = GREEN if pct < 60 else (YELLOW if pct < 85 else RED)

    return f"[{color}{bar}{RESET}] {color}{pct:5.1f}%{RESET}"


def print_system_report(snapshot: Dict[str, Any] = None, force_mock: bool = False) -> None:
    """Renders a comprehensive, styled hardware and GPU health report to terminal."""
    if snapshot is None:
        if force_mock:
            from system_software.gpu.mock import get_mock_gpu_info
            cpu = get_cpu_info(interval=0.1)
            mem = get_memory_info()
            disk = get_disk_info()
            battery = get_battery_info()
            net = get_network_info()
            gpu = get_mock_gpu_info()
            top_procs = list_top_processes(limit=5)
            health = system_service.evaluate_health(cpu, mem, disk, gpu)
            snapshot = {
                "health": health, "cpu": cpu, "memory": mem, "disk": disk,
                "battery": battery, "network": net, "gpu": gpu, "top_processes": top_procs
            }
        else:
            snapshot = system_service.get_system_snapshot()

    health = snapshot["health"]
    cpu = snapshot["cpu"]
    mem = snapshot["memory"]
    disk = snapshot["disk"]
    bat = snapshot["battery"]
    net = snapshot["network"]
    gpus = snapshot["gpu"]
    procs = snapshot["top_processes"]

    status_color = GREEN if health["status"] == "HEALTHY" else (YELLOW if health["status"] == "WARNING" else RED)

    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}               RIVA-AGI SYSTEM SOFTWARE & TELEMETRY                   {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}")
    print(f"Overall Status: {status_color}{BOLD}{health['status']}{RESET}")

    if health.get("alerts"):
        print(f"\n{BOLD}{YELLOW}Active Alerts:{RESET}")
        for alert in health["alerts"]:
            print(f"  • {alert}")

    # CPU Section
    print(f"\n{BOLD}[CPU — {cpu.get('processor') or cpu.get('architecture')}]{RESET}")
    print(f"  Overall Load:   {create_progress_bar(cpu['usage_percent'])}")
    print(f"  Cores Topology: {cpu['physical_cores']} Physical | {cpu['total_cores']} Logical")
    if cpu.get("frequency_mhz", {}).get("current"):
        print(f"  Frequency:      {cpu['frequency_mhz']['current']} MHz")

    # RAM / Memory Section
    print(f"\n{BOLD}[RAM & Virtual Memory]{RESET}")
    print(f"  RAM Usage:      {create_progress_bar(mem['percent'])}  ({mem['used_gb']} GB / {mem['total_gb']} GB)")
    print(f"  Available RAM:  {mem['available_gb']} GB (Free: {mem['free_gb']} GB)")
    if mem.get("swap", {}).get("total_gb", 0) > 0:
        print(f"  Swap Usage:     {create_progress_bar(mem['swap']['percent'])}  ({mem['swap']['used_gb']} GB / {mem['swap']['total_gb']} GB)")

    # Storage Partitions Section
    print(f"\n{BOLD}[Storage & Filesystem]{RESET}")
    for part in disk.get("partitions", [])[:3]:
        print(f"  {part['mountpoint']:<10}      {create_progress_bar(part['percent'])}  ({part['used_gb']} GB / {part['total_gb']} GB)")
    io = disk.get("io_stats", {})
    if io.get("read_bytes_mb") or io.get("write_bytes_mb"):
        print(f"  Disk I/O:       Read: {io.get('read_bytes_mb', 0)} MB | Write: {io.get('write_bytes_mb', 0)} MB")

    # NVIDIA GPU Section
    print(f"\n{BOLD}[NVIDIA GPU Telemetry]{RESET}")
    for g in gpus:
        if not g.get("has_gpu"):
            print(f"  {DIM}{g.get('name')}: {g.get('error')}{RESET}")
        else:
            print(f"  {BOLD}GPU {g['id']}: {g['name']}{RESET} (Driver: {g.get('driver_version')})")
            print(f"    Compute Load: {create_progress_bar(g['load_percent'])}")
            print(f"    VRAM Usage:   {create_progress_bar(g['memory_percent'])}  ({int(g['memory_used_mb'])} MB / {int(g['memory_total_mb'])} MB)")
            print(f"    Thermal:      {g['temperature_c']}°C  | Power: {g.get('power_draw_w', 0.0)} W")

    # Battery & Power
    print(f"\n{BOLD}[Power & Battery]{RESET}")
    if bat.get("has_battery"):
        status_str = "Charging" if bat.get("plugged_in") else "On Battery"
        print(f"  Battery Level:  {create_progress_bar(bat['percent'], reverse_colors=True)}  ({status_str})")
        print(f"  Estimated Life: {bat.get('time_remaining_str')}")
    else:
        print(f"  Status:         {bat.get('status')}")

    # Top Resource-Consuming Processes
    if procs:
        print(f"\n{BOLD}[Top Resource Consumers]{RESET}")
        print(f"  {'PID':<8} {'Process Name':<24} {'Memory %':<10} {'CPU %':<8} {'Status':<10}")
        print(f"  {'-'*64}")
        for p in procs:
            print(f"  {p['pid']:<8} {p['name'][:22]:<24} {p['memory_percent']:<10.1f} {p['cpu_percent']:<8.1f} {p['status']:<10}")

    print(f"\n{BOLD}{CYAN}======================================================================{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Riva-AGI System Software & Hardware Telemetry CLI")
    parser.add_argument("--json", action="store_true", help="Output raw telemetry as JSON")
    parser.add_argument("--mock-gpu", action="store_true", help="Simulate NVIDIA GPU metrics (useful for non-GPU dev)")
    parser.add_argument("--watch", type=int, default=0, help="Continuously poll every N seconds (e.g. --watch 2)")
    args = parser.parse_args()

    while True:
        if args.json:
            snapshot = system_service.get_system_snapshot()
            if args.mock_gpu:
                from system_software.gpu.mock import get_mock_gpu_info
                snapshot["gpu"] = get_mock_gpu_info()
            print(json.dumps(snapshot, indent=2))
        else:
            print_system_report(force_mock=args.mock_gpu)

        if args.watch <= 0:
            break
        try:
            time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nExiting monitor.")
            break


if __name__ == "__main__":
    main()
