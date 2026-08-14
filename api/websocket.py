import json
import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("agent_orchestrator.api.websocket")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # task_id -> set of websockets
    
    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        self.active_connections[task_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
    
    async def broadcast_to_task(self, task_id: str, data: dict):
        if task_id in self.active_connections:
            disconnected = []
            for ws in self.active_connections[task_id]:
                try:
                    await ws.send_json(data)
                except:
                    disconnected.append(ws)
            for ws in disconnected:
                self.active_connections[task_id].discard(ws)

manager = ConnectionManager()
