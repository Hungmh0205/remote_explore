import shutil
import psutil
import ctypes
import os
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class SystemStats(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_total: int
    disk_percent: float
    disk_free: int
    disk_total: int
    net_sent: int
    net_recv: int
    is_admin: bool
    server_pid: int

def is_user_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

import time

# Cache for system stats to prevent noisy micro-sampling
_LAST_STATS = None
_LAST_TIME = 0
_CACHE_DURATION = 1.0  # Seconds. Task Manager standard is usually 1s.

import time
import threading

# Global stats storage
_LATEST_STATS = None
_MONITOR_THREAD = None
_LOCK = threading.Lock()

def _monitor_loop():
    global _LATEST_STATS
    while True:
        try:
            # interval=1 means we measure usage over 1 second. 
            # This is blocking for this thread, which is fine.
            # It gives very stable, accurate readings matching Task Manager.
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            
            # Disk Usage
            try:
                disk = shutil.disk_usage("C:\\")
                disk_percent = round((1 - disk.free / disk.total) * 100, 1) if disk.total > 0 else 0.0
                disk_data = (disk.total, disk.free, disk_percent)
            except:
                disk_data = (0, 0, 0.0)

            net = psutil.net_io_counters()
            
            # Update global atomically-ish
            _LATEST_STATS = SystemStats(
                cpu_percent=cpu,
                memory_percent=mem.percent,
                memory_used=mem.used,
                memory_total=mem.total,
                disk_percent=disk_data[2],
                disk_free=disk_data[1],
                disk_total=disk_data[0],
                net_sent=net.bytes_sent,
                net_recv=net.bytes_recv,
                is_admin=is_user_admin(),
                server_pid=os.getpid()
            )
            
        except Exception as e:
            print(f"Monitor thread error: {e}")
            time.sleep(1) # Prevent tight loop on error

def start_monitor_if_needed():
    global _MONITOR_THREAD
    with _LOCK:
        if _MONITOR_THREAD is None or not _MONITOR_THREAD.is_alive():
            _MONITOR_THREAD = threading.Thread(target=_monitor_loop, daemon=True)
            _MONITOR_THREAD.start()

@router.get("/monitor/stats", response_model=SystemStats)
def get_stats():
    """Get current system resource usage from background monitor."""
    start_monitor_if_needed()
    
    # Return latest available, or strict fallback if first run
    if _LATEST_STATS is None:
        # Quick fallback for first immediate call
        return SystemStats(
            cpu_percent=0.0, memory_percent=0.0, memory_used=0, memory_total=0,
            disk_percent=0.0, disk_free=0, disk_total=0, net_sent=0, net_recv=0,
            is_admin=is_user_admin(),
            server_pid=os.getpid()
        )
        
    return _LATEST_STATS
