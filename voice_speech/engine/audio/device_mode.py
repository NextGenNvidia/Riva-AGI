"""
Audio device output mode detection (Earphones vs Speaker) for PipeWire / PulseAudio on Linux.
"""

import logging
import re
import subprocess

logger = logging.getLogger("riva.audio.device_mode")


def detect_output_mode() -> str:
    """
    Detect whether the active default audio output device is earphones/headphones or built-in speakers.

    Returns:
        "earphones" | "speaker"
    """
    try:
        # 1. Get default sink name
        sink_proc = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        default_sink = sink_proc.stdout.strip()
        if not default_sink:
            return "speaker"

        # Bluetooth devices (BlueZ) are almost always headphones/earphones/headsets
        if "bluez" in default_sink.lower():
            logger.info(f"Bluetooth device detected ({default_sink}) -> mode: earphones")
            return "earphones"

        # 2. Inspect sink details
        sinks_proc = subprocess.run(
            ["pactl", "list", "sinks"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        sinks_output = sinks_proc.stdout

        # Split output by Sink blocks
        sink_blocks = re.split(r"\n(?=Sink #)", sinks_output)
        for block in sink_blocks:
            if f"Name: {default_sink}" in block:
                # Check Active Port in this block
                active_port_match = re.search(r"Active Port:\s*([^\n]+)", block)
                if active_port_match:
                    active_port = active_port_match.group(1).lower()
                    if any(hp in active_port for hp in ["headphone", "headset", "earphone"]):
                        logger.info(f"Active sink port '{active_port}' -> mode: earphones")
                        return "earphones"
                    if "speaker" in active_port:
                        logger.info(f"Active sink port '{active_port}' -> mode: speaker")
                        return "speaker"

                # Check device description / form factor
                if any(k in block.lower() for k in ["headphone", "headset", "earphone", "airpod", "buds"]):
                    logger.info(f"Headphone keywords found in sink description -> mode: earphones")
                    return "earphones"

        logger.info(f"Default sink '{default_sink}' detected as speaker.")
        return "speaker"

    except Exception as e:
        logger.warning(f"Failed to detect audio output device mode ({e}), defaulting to speaker.")
        return "speaker"
