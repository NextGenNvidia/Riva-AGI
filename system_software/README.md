# System Software & Hardware Telemetry (Track 4)

The **System Software** subsystem provides real-time hardware telemetry, NVIDIA GPU health metrics, OS process monitoring, and proactive resource alerts for **Riva-AGI**.

Developed by **Anushka Gupta** & **Tooba Ashfaque** (System Software Track).

---

## Architecture Overview

```
system_software/
├── config.py             # Threshold configurations & environment variable overrides
├── service.py            # Central SystemSoftwareService & health assessment engine
├── cli.py                # Colorized interactive terminal dashboard
├── hardware/             # Host hardware telemetry
│   ├── cpu.py            # CPU usage, frequency, topology, per-core metrics
│   ├── memory.py         # Virtual memory & swap statistics
│   ├── disk.py           # Partition capacity, free space, and I/O counters
│   ├── battery.py        # Power supply & battery runtime estimation
│   └── network.py        # Network interfaces & packet/bandwidth throughput
├── gpu/                  # GPU acceleration telemetry
│   ├── nvidia.py         # Direct nvidia-smi / NVML parsing (VRAM, compute %, thermal)
│   └── mock.py           # Simulated GPU metrics for non-GPU / CI environments
├── process/              # OS process governance
│   └── manager.py        # Top resource-consuming processes and PID inspector
└── tests/                # Automated pytest unit test suite
```

---

## Key Features

1. **NVIDIA GPU Telemetry**:
   - Queries `nvidia-smi` across all installed GPUs.
   - Extracts compute utilization, VRAM usage (used/free/total), temperature, power draw (Watts), and driver version.
   - Includes graceful fallback for non-GPU machines and deterministic mock mode (`MOCK_NVIDIA_GPU=1` or `--mock-gpu`).

2. **System Resource Governance & Health Assessment**:
   - Computes overall health verdict (`HEALTHY`, `WARNING`, `CRITICAL`).
   - Automatically issues alerts if CPU, RAM, Disk, or GPU thresholds are breached.

3. **Multi-Agent Tool Integration**:
   - Directly registered with the Riva-AGI tool registry in `orchestration/tools/builtin/system_software_tools.py`.
   - Autonomous agents (`devops`, `coder`, `reasoner`) can query real hardware state during execution loops.

4. **Backward Compatibility**:
   - Provides root `system_monitor.py` adapter to support existing backend routers (e.g., PR #54 `Backend/services/system_service.py`).

---

## Quickstart & CLI Usage

### 1. Run Interactive Terminal Dashboard
```bash
python -m system_software
```

### 2. Output Raw Telemetry as JSON
```bash
python -m system_software --json
```

### 3. Continuous Live Monitoring
```bash
python -m system_software --watch 2
```

### 4. Simulate NVIDIA GPU (Testing on Non-GPU Machines)
```bash
python -m system_software --mock-gpu
```

---

## Python API Usage

```python
from system_software import system_service, get_cpu_info, get_gpu_info

# 1. Quick synchronous snapshot
snapshot = system_service.get_system_snapshot()
print("Health Status:", snapshot["health"]["status"])
print("CPU Usage:", snapshot["cpu"]["usage_percent"], "%")

# 2. Async non-blocking snapshot (for FastAPI backends)
async def fetch_telemetry():
    snapshot = await system_service.get_system_snapshot_async()
    return snapshot

# 3. Direct GPU queries
gpus = get_gpu_info()
for gpu in gpus:
    print(f"{gpu['name']}: {gpu['memory_percent']}% VRAM used")
```

---

## Testing

Run the test suite:
```bash
pytest system_software/tests/
```
