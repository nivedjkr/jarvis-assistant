"""
System Resource Monitoring Module for JARVIS
Queries real system statistics using psutil and pynvml/nvidia-smi fallback.
Tracks resource anomalies and internet connectivity status.
"""

import subprocess
import socket
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import psutil

import warnings
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False


class SystemMonitor:
    """Manages real-time hardware telemetry, threshold checking, and anomaly tracking."""

    def __init__(self, gpu_temp_threshold: float = 85.0):
        self.gpu_temp_threshold = gpu_temp_threshold
        self.consecutive_high_cpu_count = 0
        self.last_network_online: Optional[bool] = None
        self.anomaly_log: List[Dict[str, Any]] = []
        
        # Initialize NVML if available
        self.nvml_initialized = False
        if HAS_PYNVML:
            try:
                pynvml.nvmlInit()
                self.nvml_initialized = True
            except Exception:
                self.nvml_initialized = False

    def get_gpu_stats(self) -> Optional[Dict[str, Any]]:
        """
        Query real NVIDIA GPU stats via pynvml or nvidia-smi fallback.
        Returns None if no NVIDIA GPU is detected or available.
        """
        # Try pynvml first
        if self.nvml_initialized:
            try:
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode('utf-8')
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    
                    return {
                        "name": name,
                        "temp_c": float(temp),
                        "gpu_util_pct": float(util.gpu),
                        "mem_used_mb": float(mem.used / (1024 * 1024)),
                        "mem_total_mb": float(mem.total / (1024 * 1024)),
                        "mem_util_pct": float((mem.used / mem.total) * 100.0)
                    }
            except Exception:
                pass

        # Fallback to nvidia-smi CLI
        try:
            cmd = ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 5:
                    name = parts[0]
                    temp = float(parts[1])
                    util = float(parts[2])
                    mem_used = float(parts[3])
                    mem_total = float(parts[4])
                    return {
                        "name": name,
                        "temp_c": temp,
                        "gpu_util_pct": util,
                        "mem_used_mb": mem_used,
                        "mem_total_mb": mem_total,
                        "mem_util_pct": (mem_used / mem_total) * 100.0 if mem_total > 0 else 0.0
                    }
        except Exception:
            pass

        return None

    def check_network_connectivity(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> bool:
        """Perform a real socket connection test to verify internet access."""
        try:
            socket.setdefaulttimeout(timeout)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            s.close()
            return True
        except Exception:
            return False

    def get_system_snapshot(self) -> Dict[str, Any]:
        """Fetch a complete real-time resource snapshot."""
        cpu_pct = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        
        # Disk stats across all physical partitions
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent_used": usage.percent,
                    "percent_free": round(100.0 - usage.percent, 1)
                })
            except Exception:
                continue

        gpu_stats = self.get_gpu_stats()
        is_online = self.check_network_connectivity()

        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_pct": cpu_pct,
            "ram_pct": ram.percent,
            "ram_used_gb": round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "disks": disks,
            "gpu": gpu_stats,
            "network_online": is_online
        }

    def evaluate_resource_anomalies(self) -> List[Dict[str, Any]]:
        """
        Evaluate real live telemetry against threshold rules.
        Returns a list of newly triggered alert events (if any).
        """
        alerts = []
        now_dt = datetime.now()
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 1. CPU check (sustained > 85% for 2+ consecutive checks)
        cpu_pct = psutil.cpu_percent(interval=0.2)
        if cpu_pct > 85.0:
            self.consecutive_high_cpu_count += 1
            if self.consecutive_high_cpu_count >= 2:
                duration_sec = self.consecutive_high_cpu_count * 2
                msg = f"CPU usage sustained at {cpu_pct:.1f}% for {duration_sec} seconds, sir."
                alert = {"type": "cpu", "level": "warning", "message": msg, "timestamp": now_str}
                alerts.append(alert)
                self.anomaly_log.append(alert)
        else:
            self.consecutive_high_cpu_count = 0

        # 2. RAM check (> 90%)
        ram = psutil.virtual_memory()
        if ram.percent > 90.0:
            msg = f"RAM usage critical at {ram.percent:.1f}% ({round(ram.used / (1024**3), 1)} GB / {round(ram.total / (1024**3), 1)} GB), sir."
            alert = {"type": "ram", "level": "critical", "message": msg, "timestamp": now_str}
            alerts.append(alert)
            self.anomaly_log.append(alert)

        # 3. GPU check (temp > threshold)
        gpu = self.get_gpu_stats()
        if gpu and gpu["temp_c"] >= self.gpu_temp_threshold:
            msg = f"GPU temperature elevated at {gpu['temp_c']:.0f}°C on {gpu['name']}, sir."
            alert = {"type": "gpu", "level": "warning", "message": msg, "timestamp": now_str}
            alerts.append(alert)
            self.anomaly_log.append(alert)

        # 4. Disk space check (< 10% free on any drive)
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                pct_free = 100.0 - usage.percent
                if pct_free < 10.0:
                    msg = f"Disk space low on {part.mountpoint}: only {pct_free:.1f}% ({round(usage.free / (1024**3), 1)} GB) remaining, sir."
                    alert = {"type": "disk", "level": "warning", "message": msg, "timestamp": now_str}
                    # Omitted from proactive voice alerts; stored for /system inspection
                    self.anomaly_log.append(alert)
            except Exception:
                continue

        # 5. Network connectivity check
        is_online = self.check_network_connectivity()
        if self.last_network_online is True and not is_online:
            msg = "Sir, internet connection lost."
            alert = {"type": "network", "level": "critical", "message": msg, "timestamp": now_str}
            alerts.append(alert)
            self.anomaly_log.append(alert)
        elif self.last_network_online is False and is_online:
            msg = "Sir, internet connection restored."
            alert = {"type": "network", "level": "info", "message": msg, "timestamp": now_str}
            alerts.append(alert)
            self.anomaly_log.append(alert)
            
        self.last_network_online = is_online

        return alerts

    def get_recent_anomalies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent recorded resource anomalies."""
        return self.anomaly_log[-limit:]
