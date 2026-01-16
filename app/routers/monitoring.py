import shutil
import psutil
from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..path_utils import resolve_path

router = APIRouter()

class SystemStats(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_total: int
    memory_used: int
    disk_total: int
    disk_free: int
    disk_percent: float

@router.get("/monitor/stats", response_model=SystemStats)
def get_system_stats(path: str = Query(".")):
    """
    Returns system stats:
    - CPU usage (%)
    - RAM usage (total, used, %)
    - Disk usage for the drive containing 'path' (total, free, %)
    """
    # 1. CPU & RAM
    cpu = psutil.cpu_percent(interval=None) # Non-blocking call
    mem = psutil.virtual_memory()

    # 2. Disk Usage
    # Resolve path to ensure it's valid, fallback to CWD if not
    allowed, abs_path = resolve_path(path)
    if not allowed:
        # If invalid path provided for monitoring, just use current working directory
        abs_path = "."
    
    try:
        disk = shutil.disk_usage(abs_path)
        disk_total = disk.total
        disk_free = disk.free
        # Calculate used percent
        disk_percent = 0.0
        if disk_total > 0:
            disk_percent = round((1 - disk_free / disk_total) * 100, 1)
    except Exception:
        disk_total = 0
        disk_free = 0
        disk_percent = 0.0

    return SystemStats(
        cpu_percent=cpu,
        memory_percent=mem.percent,
        memory_total=mem.total,
        memory_used=mem.used,
        disk_total=disk_total,
        disk_free=disk_free,
        disk_percent=disk_percent
    )
