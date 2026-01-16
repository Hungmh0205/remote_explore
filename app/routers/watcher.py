import asyncio
import os
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from watchfiles import awatch

from ..path_utils import resolve_path
from ..config import settings
from ..auth import SESSION_COOKIE

router = APIRouter()

@router.websocket("/ws/watcher")
async def websocket_watcher(websocket: WebSocket):
    # Auth check
    if settings.auth_enabled:
        cookie = websocket.cookies.get(SESSION_COOKIE)
        if cookie != "1":
            await websocket.close(code=1008, reason="Unauthorized")
            return

    await websocket.accept()
    
    current_watch_task = None
    stop_event = asyncio.Event()

    async def watch_folder(path: str):
        try:
            # awatch is an async generator
            async for changes in awatch(path, stop_event=stop_event):
                # 'changes' is a set of (ChangeType, path_string)
                # We just notify client that "something changed" so it can reload
                if websocket.client_state == WebSocket.CONNECTED:
                    # We send a simple message. Client decides what to do (usually reload list)
                    await websocket.send_text("change")
                else:
                    break
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            message = {}
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue

            action = message.get("action")
            
            if action == "watch":
                path_to_watch = message.get("path")
                allowed, abs_path = resolve_path(path_to_watch)
                
                if allowed and os.path.isdir(abs_path):
                    # Stop previous watcher if exists
                    if current_watch_task:
                        stop_event.set() # Signal awatch to stop
                        try:
                            await current_watch_task
                        except:
                            pass
                        stop_event.clear() # Reset for next use
                    
                    # Start new watcher
                    current_watch_task = asyncio.create_task(watch_folder(abs_path))
                else:
                    # Invalid path, maybe stop watching?
                    pass

    except WebSocketDisconnect:
        pass
    finally:
        if current_watch_task:
            stop_event.set()
            try:
                await current_watch_task
            except:
                pass
