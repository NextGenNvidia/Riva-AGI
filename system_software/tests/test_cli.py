"""Unit tests for CLI progress bar and reporting functions."""

from system_software.cli import create_progress_bar, print_system_report


def test_create_progress_bar():
    bar_25 = create_progress_bar(25.0, length=20)
    assert "25.0%" in bar_25
    assert "█" in bar_25
    assert "░" in bar_25

    bar_100 = create_progress_bar(100.0, length=10)
    assert "100.0%" in bar_100
    assert "░" not in bar_100


def test_print_system_report(capsys):
    print_system_report(force_mock=True)
    captured = capsys.readouterr()
    assert "RIVA-AGI SYSTEM SOFTWARE & TELEMETRY" in captured.out
    assert "Overall Status" in captured.out
    assert "CPU" in captured.out
    assert "RAM" in captured.out
