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

    # 2. Spawn the process (cmd.exe)
    # dimensions=(rows, cols)
    try:
        proc = PtyProcess.spawn("cmd.exe", dimensions=(24, 80))
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
