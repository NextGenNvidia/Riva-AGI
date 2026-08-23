"""
Audio device query and validation utilities.
"""

from typing import List, Dict, Any, Optional
import sounddevice as sd


def list_audio_devices() -> List[Dict[str, Any]]:
    """Return all available audio devices with their details."""
    devices = sd.query_devices()
    result = []
    for idx, dev in enumerate(devices):
        result.append({
            "index": idx,
            "name": dev.get("name", "Unknown"),
            "max_input_channels": dev.get("max_input_channels", 0),
            "max_output_channels": dev.get("max_output_channels", 0),
            "default_samplerate": dev.get("default_samplerate", 44100),
        })
    return result


def get_default_devices() -> Dict[str, Optional[int]]:
    """Return default input and output device indices."""
    try:
        default_in, default_out = sd.default.device
        return {"input": default_in, "output": default_out}
    except Exception:
        return {"input": None, "output": None}


def find_echo_cancel_devices() -> Dict[str, Optional[int]]:
    """Automatically find OS-level WebRTC echo cancellation devices if loaded."""
    devices = sd.query_devices()
    aec_in = None
    aec_out = None

    for idx, d in enumerate(devices):
        name = d.get("name", "").lower()
        if "echo-cancel" in name or "echocancel" in name:
            if d.get("max_input_channels", 0) > 0 and aec_in is None and "playback" not in name:
                aec_in = idx
            if d.get("max_output_channels", 0) > 0 and aec_out is None and "capture" not in name:
                aec_out = idx

    return {"input": aec_in, "output": aec_out}


def print_audio_devices_summary() -> None:
    """Print a clean summary of available audio devices."""
    print("--- Available Audio Devices ---")
    devices = list_audio_devices()
    defaults = get_default_devices()
    aec = find_echo_cancel_devices()
    for dev in devices:
        in_ch = dev["max_input_channels"]
        out_ch = dev["max_output_channels"]
        tags = []
        if dev["index"] == defaults.get("input"):
            tags.append("DEFAULT IN")
        if dev["index"] == defaults.get("output"):
            tags.append("DEFAULT OUT")
        if dev["index"] == aec.get("input"):
            tags.append("AEC IN")
        if dev["index"] == aec.get("output"):
            tags.append("AEC OUT")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"[{dev['index']:2d}] {dev['name']} (In: {in_ch}, Out: {out_ch}){tag_str}")
    print("-------------------------------")
