"""
WebSocket endpoint — 将事件总线中的事件广播给所有连接的前端客户端。
"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from study_agent.event_bus import Event, event_bus

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器。"""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """接受并保存连接。"""
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """移除连接。"""
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, event: Event) -> None:
        """广播事件到所有客户端。"""
        payload = json.dumps(
            {
                "type": event.type.value,
                "data": event.data,
                "timestamp": event.timestamp,
            },
            ensure_ascii=False,
        )
        for websocket in self.active[:]:
            try:
                await websocket.send_text(payload)
            except Exception:
                self.disconnect(websocket)


manager = ConnectionManager()

event_bus.subscribe(manager.broadcast)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """事件 WebSocket。"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
