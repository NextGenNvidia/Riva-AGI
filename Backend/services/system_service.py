"""System Telemetry Service for Riva-AGI.

Collects CPU, memory, battery, and GPU hardware metrics using psutil and nvidia-smi.
Non-blocking operations run in worker threads.
"""

import asyncio
from typing import Any, Dict, List
import system_monitor


class SystemService:
    """Provides system telemetry data."""

    @staticmethod
    async def get_cpu_info() -> Dict[str, Any]:
        """Runs CPU sampling in a separate thread so it does not block the async event loop."""
        return await asyncio.to_thread(system_monitor.get_cpu_info)

    @staticmethod
    def get_memory_info() -> Dict[str, Any]:
        """Returns RAM usage statistics."""
        return system_monitor.get_memory_info()

    @staticmethod
    def get_battery_info() -> Dict[str, Any]:
        """Returns battery status and percentage."""
        return system_monitor.get_battery_info()

    @staticmethod
    def get_gpu_info() -> List[Dict[str, Any]]:
        """Returns GPU hardware metrics."""
        return system_monitor.get_gpu_info()

    async def get_all_metrics(self) -> Dict[str, Any]:
        """Fetches all system telemetry data concurrently."""
        cpu = await self.get_cpu_info()
        mem = self.get_memory_info()
        battery = self.get_battery_info()
        gpu = self.get_gpu_info()

        return {
            "cpu": cpu,
            "memory": mem,
            "battery": battery,
            "gpu": gpu,
        }


# Global singleton instance
system_service = SystemService()
