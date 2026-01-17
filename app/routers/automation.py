import asyncio
import os
import uuid
import datetime
import traceback
import subprocess
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()

SCRIPTS_DIR = os.path.join(os.getcwd(), "server_scripts")
os.makedirs(SCRIPTS_DIR, exist_ok=True)

from ..db import execute, query_all, query_one

class ScriptMetadata(BaseModel):
    name: str
    filename: str
    description: str = ""
    color: str = "blue"  # blue, red, green, yellow, gray
    type: str  # ps1, bat, py

class JobInfo(BaseModel):
    id: str
    script: str
    status: str  # running, success, failed
    start_time: str
    end_time: Optional[str] = None
    exit_code: Optional[int] = None
    log: str = ""

def _parse_metadata(path: str, filename: str) -> ScriptMetadata:
    """Read first few lines of file to find @Title, @Description, @Color."""
    desc = ""
    title = filename
    color = "blue"
    
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i in range(10): # Check first 10 lines
                line = f.readline()
                if not line: break
                line = line.strip()
                # Parse comments like REM, #, etc.
                if "@Title:" in line:
                    title = line.split("@Title:", 1)[1].strip()
                if "@Description:" in line:
                    desc = line.split("@Description:", 1)[1].strip()
                if "@Color:" in line:
                    color = line.split("@Color:", 1)[1].strip()
    except:
        pass

    ext = filename.split(".")[-1].lower()
    return ScriptMetadata(name=title, filename=filename, description=desc, color=color, type=ext)

@router.get("/automation/scripts", response_model=List[ScriptMetadata])
def list_scripts():
    scripts = []
    if not os.path.exists(SCRIPTS_DIR):
        return []
        
    for f in os.listdir(SCRIPTS_DIR):
        if f.lower().endswith(('.bat', '.ps1', '.py', '.cmd')):
            full_path = os.path.join(SCRIPTS_DIR, f)
            scripts.append(_parse_metadata(full_path, f))
    return scripts

async def _run_script_task(job_id: str, filename: str):
    """Async background task to run the script and capture output."""
    script_path = os.path.join(SCRIPTS_DIR, filename)
    
    cmd = []
    if filename.endswith(".ps1"):
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path]
    elif filename.endswith(".py"):
        import sys
        cmd = [sys.executable, script_path] 
    elif filename.endswith((".bat", ".cmd")):
         cmd = ["cmd", "/c", script_path]
    
    def run_sync():
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace"
        )

    exit_code = -1
    log_output = ""
    status = "failed"
    end_time = datetime.datetime.now().isoformat()

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_sync)
        
        exit_code = result.returncode
        log_output = result.stdout or ""
        status = "success" if result.returncode == 0 else "failed"
        
    except Exception as e:
        log_output = f"Internal Error: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        status = "failed"
    
    end_time = datetime.datetime.now().isoformat()
    
    # Update DB
    execute(
        "UPDATE jobs SET status=?, end_time=?, exit_code=?, log=? WHERE id=?",
        (status, end_time, exit_code, log_output, job_id)
    )

@router.post("/automation/run/{filename}")
async def run_script(filename: str, background_tasks: BackgroundTasks):
    path = os.path.join(SCRIPTS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Script not found")
        
    job_id = str(uuid.uuid4())
    start_time = datetime.datetime.now().isoformat()
    
    # Insert initial job record
    execute(
        "INSERT INTO jobs(id, script, status, start_time, log) VALUES(?,?,?,?,?)",
        (job_id, filename, "running", start_time, "Job queued...\n")
    )
    
    # Run in background
    background_tasks.add_task(_run_script_task, job_id, filename)
    
    return {"ok": True, "job_id": job_id}

@router.get("/automation/jobs/{job_id}", response_model=JobInfo)
def get_job(job_id: str):
    row = query_one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobInfo(**row)

@router.get("/automation/history", response_model=List[JobInfo])
def get_history():
    # Return last 20 jobs, sorted new to old
    rows = query_all("SELECT * FROM jobs ORDER BY start_time DESC LIMIT 20")
    return [JobInfo(**r) for r in rows]

@router.delete("/automation/jobs/{job_id}")
def delete_job(job_id: str):
    execute("DELETE FROM jobs WHERE id=?", (job_id,))
    return {"ok": True}
