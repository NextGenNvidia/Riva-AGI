"""Unit tests for system_software.gpu telemetry."""

import subprocess
from unittest.mock import patch, MagicMock
import pytest

from system_software.gpu.nvidia import get_gpu_info, is_nvidia_smi_available
from system_software.gpu.mock import get_mock_gpu_info


def test_get_mock_gpu_info():
    mock_gpus = get_mock_gpu_info()
    assert isinstance(mock_gpus, list)
    assert len(mock_gpus) == 1
    gpu = mock_gpus[0]
    assert gpu["has_gpu"] is True
    assert "A100" in gpu["name"]
    assert gpu["memory_total_mb"] == 81920.0
    assert gpu["temperature_c"] == 52


def test_get_gpu_info_with_mock_forced():
    gpus = get_gpu_info(force_mock=True)
    assert isinstance(gpus, list)
    assert len(gpus) == 1
    assert gpus[0]["has_gpu"] is True
    assert gpus[0]["memory_total_mb"] > 0


def test_get_gpu_info_fallback_non_nvidia():
    with patch("system_software.gpu.nvidia.is_nvidia_smi_available", return_value=False):
        gpus = get_gpu_info(force_mock=False)
        assert isinstance(gpus, list)
        assert len(gpus) == 1
        assert gpus[0]["has_gpu"] is False
        assert "not found" in gpus[0]["error"].lower()


def test_get_gpu_info_successful_nvidia_smi_parsing():
    fake_csv_output = (
        "0, NVIDIA GeForce RTX 4090, 45, 8192, 24576, 16384, 58, 220.5, 550.54.14\n"
    )
    mock_proc = MagicMock()
    mock_proc.stdout = fake_csv_output
    mock_proc.returncode = 0

    with patch("system_software.gpu.nvidia.is_nvidia_smi_available", return_value=True), \
         patch("subprocess.run", return_value=mock_proc):
        gpus = get_gpu_info(force_mock=False)
        assert len(gpus) == 1
        gpu = gpus[0]
        assert gpu["has_gpu"] is True
        assert gpu["id"] == 0
        assert "RTX 4090" in gpu["name"]
        assert gpu["load_percent"] == 45.0
        assert gpu["memory_used_mb"] == 8192.0
        assert gpu["memory_total_mb"] == 24576.0
        assert gpu["memory_free_mb"] == 16384.0
        assert gpu["temperature_c"] == 58
        assert gpu["power_draw_w"] == 220.5
        assert gpu["driver_version"] == "550.54.14"
