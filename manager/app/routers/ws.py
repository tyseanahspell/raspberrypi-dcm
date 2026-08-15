import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.events import bus
from app.security import decode_access_token

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    if not decode_access_token(token):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    queue = bus.subscribe()
    try:
        await websocket.send_text(json.dumps({"type": "ready", "payload": {}}))
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=25)
                await websocket.send_text(json.dumps(message, default=str))
            except TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping", "payload": {}}))
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)
