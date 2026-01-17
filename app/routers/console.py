import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

# Try importing winpty, handle error if user hasn't installed it yet
try:
    from winpty import PtyProcess
except ImportError:
    PtyProcess = None

from ..config import settings
from ..auth import SESSION_COOKIE

router = APIRouter()

@router.websocket("/ws/console")
async def websocket_console(websocket: WebSocket):
    # 1. Auth Check (Basic Cookie Check similar to HTTP endpoints)
    if settings.auth_enabled:
        cookie = websocket.cookies.get(SESSION_COOKIE)
        if cookie != "1":
            await websocket.close(code=1008, reason="Unauthorized")
            return

    await websocket.accept()

    if PtyProcess is None:
        await websocket.send_text("Error: 'pywinpty' library not found on server. Please install it: pip install pywinpty")
        await websocket.close()
        return

    # dimensions=(rows, cols)
    cwd = os.getcwd()
    try:
        # "Lối đi mới 2.0": PowerShell + Clean Registry Environment
        # We reconstruct the environment from Windows Registry to ensure it's identical
        # to a fresh local session, removing any Server Venv pollution.
        env = os.environ.copy()
        
        # 1. Cleanup vars
        if "VIRTUAL_ENV" in env:
            del env["VIRTUAL_ENV"]
        
        # 2. Reconstruct PATH from Registry (True Cleanliness)
        try:
            import winreg
            # Load System PATH
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment') as key:
                sys_path, _ = winreg.QueryValueEx(key, 'Path')
            
            # Load User PATH
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment') as key:
                user_path, _ = winreg.QueryValueEx(key, 'Path')
            
            # Combine
            full_path = f"{sys_path};{user_path}"
            # Expand variables (like %SystemRoot%)
            env["PATH"] = os.path.expandvars(full_path)
        except Exception:
            # Fallback: Just keep existing PATH if registry fails
            pass

        # 3. Spawn PowerShell (Clean ENV + CWD)
        proc = PtyProcess.spawn("powershell.exe -NoLogo", cwd=cwd, env=env, dimensions=(24, 80))
    except Exception as e:
        await websocket.send_text(f"Error spawning process: {str(e)}")
        await websocket.close()
        return

    # Helper to set UTF-8 mode for cmd (optional but recommended for visual artifacts)
    try:
        proc.write("chcp 65001\r\n")
        # Clear the initial output artifacts from chcp if possible, 
        # but usually it just shows up in the terminal, which is fine.
    except:
        pass

    loop = asyncio.get_event_loop()

    async def read_from_pty():
        """Reads from PTY in a separate thread to avoid blocking event loop."""
        while proc.isalive():
            try:
                # pty.read is blocking, so run in executor
                output = await loop.run_in_executor(None, proc.read, 1024)
                if not output:
                    break
                # Check WS state before sending
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(output)
                else:
                    break
            except Exception:
                break
        # If PTY dies, close WS
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

    async def write_to_pty():
        """Reads from WebSocket and writes to PTY."""
        try:
            while True:
                data = await websocket.receive_text()
                # Check if it's a resize command (JSON) or raw input
                # We assume resize commands are JSON starting with {
                if data.startswith("{"):
                    try:
                        cmd = json.loads(data)
                        if cmd.get("type") == "resize":
                            cols = cmd.get("cols", 80)
                            rows = cmd.get("rows", 24)
                            proc.setwinsize(rows, cols)
                            continue
                    except json.JSONDecodeError:
                        pass # Not JSON, treat as raw input
                
                # Write raw input to PTY
                proc.write(data)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    # 3. Run both loops concurrently
    # logic: if either task finishes (WS disconnects OR PTY dies), we terminate everything.
    read_task = asyncio.create_task(read_from_pty())
    write_task = asyncio.create_task(write_to_pty())

    done, pending = await asyncio.wait(
        [read_task, write_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # 4. Cleanup
    for task in pending:
        task.cancel() 
    
    # Kill the process forcefully to prevent zombie cmd.exe processes
    proc.terminate()
