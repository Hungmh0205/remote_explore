import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()

class ProcessInfo(BaseModel):
    pid: int
    name: str
    username: str = ""
    memory_mb: float
    cpu_percent: float

@router.get("/processes", response_model=List[ProcessInfo])
def list_processes(limit: int = 50):
    """List top processes by memory usage."""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'username', 'memory_info', 'cpu_percent']):
        try:
            mem_mb = p.info['memory_info'].rss / (1024 * 1024)
            procs.append(ProcessInfo(
                pid=p.info['pid'],
                name=p.info['name'],
                username=p.info['username'] or "",
                memory_mb=round(mem_mb, 2),
                cpu_percent=p.info['cpu_percent'] or 0.0
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # Sort by Memory usage desc
    procs.sort(key=lambda x: x.memory_mb, reverse=True)
    return procs[:limit]

class KillBody(BaseModel):
    pid: int

@router.post("/processes/kill")
def kill_process(body: KillBody):
    """Terminate a process by PID."""
    try:
        p = psutil.Process(body.pid)
        p.terminate()
        return {"ok": True}
    except psutil.NoSuchProcess:
        raise HTTPException(status_code=404, detail="Process not found")
    except psutil.AccessDenied:
        raise HTTPException(status_code=403, detail="Access denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
