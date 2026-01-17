
import asyncio
import aiofiles
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..config import settings

router = APIRouter()

@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    log_file = settings.log_file
    
    # Send initial content (last 20KB or so to give context)
    init_bytes = 20 * 1024
    
    try:
        # Determine file size
        if not os.path.exists(log_file):
             # If no log file, just keep connection open but silent until file appears
             await websocket.send_text("Waiting for log file...")
        else:
            file_size = os.path.getsize(log_file)
            start_pos = max(0, file_size - init_bytes)
            
            async with aiofiles.open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                await f.seek(start_pos)
                while True:
                    line = await f.readline()
                    if line:
                        await websocket.send_text(line)
                    else:
                        # No new line, wait a bit
                        await asyncio.sleep(0.5)
                        # Check if file rotated or similar? For now simple tail.
                        # Using seek to end if we just read? NO, readline at EOF returns empty string.
                        # We just stay in loop.
                        # Check file existence / rotation logic could be added here.
    except WebSocketDisconnect:
        print("Log client disconnected")
    except Exception as e:
        print(f"Log stream error: {e}")
        try:
             await websocket.close()
        except:
             pass
