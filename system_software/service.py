"""Central System Software Telemetry & Health Assessment Service."""

import asyncio
from typing import Any, Dict, List

from system_software.config import config
from system_software.hardware.cpu import get_cpu_info
from system_software.hardware.memory import get_memory_info
from system_software.hardware.disk import get_disk_info
from system_software.hardware.battery import get_battery_info
from system_software.hardware.network import get_network_info
from system_software.gpu.nvidia import get_gpu_info
from system_software.process.manager import list_top_processes


class SystemSoftwareService:
    """Provides unified system telemetry, threshold evaluations, and health verdicts."""

    def __init__(self, sys_config=None):
        self.config = sys_config or config

    def evaluate_health(
        self,
        cpu_metrics: Dict[str, Any],
        memory_metrics: Dict[str, Any],
        disk_metrics: Dict[str, Any],
        gpu_metrics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluates health thresholds across hardware and GPU metrics.
        
        Returns:
            Dict containing 'status' ('HEALTHY', 'WARNING', 'CRITICAL') and list of 'alerts'.
        """
        alerts: List[str] = []
        is_critical = False
        is_warning = False

        # CPU Evaluation
        cpu_usage = cpu_metrics.get("usage_percent", 0.0)
        if cpu_usage >= self.config.CPU_CRITICAL_THRESHOLD:
            alerts.append(f"CRITICAL: CPU usage is at {cpu_usage:.1f}% (threshold: {self.config.CPU_CRITICAL_THRESHOLD}%)")
            is_critical = True
        elif cpu_usage >= self.config.CPU_WARNING_THRESHOLD:
            alerts.append(f"WARNING: CPU usage elevated at {cpu_usage:.1f}%")
            is_warning = True

        # Memory Evaluation
        mem_usage = memory_metrics.get("percent", 0.0)
        if mem_usage >= self.config.MEMORY_CRITICAL_THRESHOLD:
            alerts.append(f"CRITICAL: RAM utilization is at {mem_usage:.1f}% (threshold: {self.config.MEMORY_CRITICAL_THRESHOLD}%)")
            is_critical = True
        elif mem_usage >= self.config.MEMORY_WARNING_THRESHOLD:
            alerts.append(f"WARNING: RAM utilization elevated at {mem_usage:.1f}%")
            is_warning = True

        # Disk Evaluation
        disk_usage = disk_metrics.get("primary_used_percent", 0.0)
        if disk_usage >= self.config.DISK_CRITICAL_THRESHOLD:
            alerts.append(f"CRITICAL: Primary disk is {disk_usage:.1f}% full")
            is_critical = True
        elif disk_usage >= self.config.DISK_WARNING_THRESHOLD:
            alerts.append(f"WARNING: Primary disk is {disk_usage:.1f}% full")
            is_warning = True

        # GPU Evaluation
        for gpu in gpu_metrics:
            if not gpu.get("has_gpu"):
                continue
            vram_usage = gpu.get("memory_percent", 0.0)
            gpu_temp = gpu.get("temperature_c", 0)

            if vram_usage >= self.config.GPU_VRAM_CRITICAL_THRESHOLD:
                alerts.append(f"CRITICAL: GPU [{gpu.get('name')}] VRAM is {vram_usage:.1f}% full")
                is_critical = True
            elif vram_usage >= self.config.GPU_VRAM_WARNING_THRESHOLD:
                alerts.append(f"WARNING: GPU [{gpu.get('name')}] VRAM usage elevated at {vram_usage:.1f}%")
                is_warning = True

            if gpu_temp >= self.config.GPU_TEMP_CRITICAL_THRESHOLD:
                alerts.append(f"CRITICAL: GPU [{gpu.get('name')}] temperature critical at {gpu_temp}°C")
                is_critical = True
            elif gpu_temp >= self.config.GPU_TEMP_WARNING_THRESHOLD:
                alerts.append(f"WARNING: GPU [{gpu.get('name')}] temperature high at {gpu_temp}°C")
                is_warning = True

        if is_critical:
            status = "CRITICAL"
        elif is_warning:
            status = "WARNING"
        else:
            status = "HEALTHY"

        return {
            "status": status,
            "alerts": alerts,
        }

    def get_system_snapshot(self) -> Dict[str, Any]:
        """Collects a complete synchronous telemetry snapshot across all subsystems."""
        cpu = get_cpu_info(interval=self.config.CPU_SAMPLE_INTERVAL)
        mem = get_memory_info()
        disk = get_disk_info()
        battery = get_battery_info()
        net = get_network_info()
        gpu = get_gpu_info()
        top_procs = list_top_processes(limit=5, sort_by="memory")
        health = self.evaluate_health(cpu, mem, disk, gpu)

        return {
            "health": health,
            "cpu": cpu,
            "memory": mem,
            "disk": disk,
            "battery": battery,
            "network": net,
            "gpu": gpu,
            "top_processes": top_procs,
        }

    async def get_system_snapshot_async(self) -> Dict[str, Any]:
        """Collects the system telemetry snapshot asynchronously without blocking the event loop."""
        return await asyncio.to_thread(self.get_system_snapshot)


# Global singleton instance
system_service = SystemSoftwareService()
