import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()

import ctypes

# Helper to find PIDs with visible windows
def get_gui_pids():
    gui_pids = set()
    try:
        def callback(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    pid = ctypes.c_ulong()
                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    gui_pids.add(pid.value)
            return True
        
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
    except Exception:
        pass # Fallback safely if anything goes wrong
    return gui_pids

class ProcessInfo(BaseModel):
    pid: int
    name: str
    username: str = ""
    memory_mb: float
    cpu_percent: float
    is_app: bool

@router.get("/processes", response_model=List[ProcessInfo])
def list_processes(limit: int = 100):
    """List processes, distinguishing apps vs background."""
    procs = []
    gui_pids = get_gui_pids()
    
    for p in psutil.process_iter(['pid', 'name', 'username', 'memory_info', 'cpu_percent']):
        try:
            mem_mb = p.info['memory_info'].rss / (1024 * 1024)
            pid = p.info['pid']
            
            # Apps are traditionally those with visible windows
            # Also include implicit "Apps" like specific interesting processes regardless of window? 
            # For now stick to strict window definition which mimics Task Manager "Apps" section roughly.
            is_app = pid in gui_pids
            
            procs.append(ProcessInfo(
                pid=pid,
                name=p.info['name'],
                username=p.info['username'] or "",
                memory_mb=round(mem_mb, 2),
                cpu_percent=p.info['cpu_percent'] or 0.0,
                is_app=is_app
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # Sort by Apps first, then Memory usage desc
    # Actually user likely wants them grouped. Sorting by memory globally first, then frontend groups.
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
