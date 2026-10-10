"""Battery and power source telemetry for Riva-AGI."""

from typing import Any, Dict

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_battery_info() -> Dict[str, Any]:
    """
    Returns battery percentage, power plugged state, and estimated runtime.
    
    Returns:
        Dict containing battery and power status.
    """
    if HAS_PSUTIL:
        battery = psutil.sensors_battery()
        if battery is None:
            return {
                "has_battery": False,
                "percent": 100.0,
                "plugged_in": True,
                "status": "No battery detected (Desktop / Server hardware / Plugged in)",
                "time_remaining_str": "AC Power",
            }

        secs_left = battery.secsleft
        if secs_left in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN) or secs_left < 0:
            time_remaining_str = "Calculating or Plugged In"
        else:
            hours = secs_left // 3600
            minutes = (secs_left % 3600) // 60
            time_remaining_str = f"{hours}h {minutes}m"

        return {
            "has_battery": True,
            "percent": round(battery.percent, 1),
            "plugged_in": battery.power_plugged,
            "status": "Charging / AC Power" if battery.power_plugged else "Discharging (Battery)",
            "time_remaining_str": time_remaining_str,
        }

    return {
        "has_battery": False,
        "percent": 100.0,
        "plugged_in": True,
        "status": "Unknown (psutil unavailable)",
        "time_remaining_str": "AC Power",
    }
