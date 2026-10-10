"""Network interfaces and bandwidth I/O telemetry for Riva-AGI."""

from typing import Any, Dict, List

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_network_info() -> Dict[str, Any]:
    """
    Returns active network interfaces, IP addresses, and I/O traffic stats.
    
    Returns:
        Dict containing network adapters and throughput counters.
    """
    interfaces: List[Dict[str, Any]] = []

    if HAS_PSUTIL:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        io = psutil.net_io_counters()

        for iface_name, addr_list in addrs.items():
            iface_stats = stats.get(iface_name)
            is_up = iface_stats.isup if iface_stats else False
            speed_mbps = iface_stats.speed if iface_stats else 0
            
            ipv4_list = []
            for a in addr_list:
                # Family 2 is AF_INET
                if str(a.family).endswith("AF_INET") or getattr(a, "family", None) == 2:
                    ipv4_list.append(a.address)

            interfaces.append({
                "interface": iface_name,
                "is_up": is_up,
                "speed_mbps": speed_mbps,
                "ipv4": ipv4_list,
            })

        io_stats = {
            "bytes_sent_mb": round(io.bytes_sent / (1024 ** 2), 2),
            "bytes_recv_mb": round(io.bytes_recv / (1024 ** 2), 2),
            "packets_sent": io.packets_sent,
            "packets_recv": io.packets_recv,
            "errin": io.errin,
            "errout": io.errout,
            "dropin": io.dropin,
            "dropout": io.dropout,
        }
    else:
        io_stats = {
            "bytes_sent_mb": 0.0,
            "bytes_recv_mb": 0.0,
            "packets_sent": 0,
            "packets_recv": 0,
            "errin": 0,
            "errout": 0,
            "dropin": 0,
            "dropout": 0,
        }

    return {
        "interfaces": interfaces,
        "io_stats": io_stats,
    }
