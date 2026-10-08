"""WebSocket Event Bus for Agnitia"""

import json
from datetime import datetime, timezone
from typing import Set
from fastapi import WebSocket


class EventBus:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def emit(self, event_type: str, payload: dict) -> None:
        """Wraps payload in the contract envelope and broadcasts to all active sockets."""
        now = datetime.now(timezone.utc).isoformat()
        envelope = {
            "type": event_type,
            "ts": now,
            "payload": payload,
        }
        message = json.dumps(envelope)

        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.add(connection)

        for dead in dead_connections:
            self.disconnect(dead)


bus = EventBus()


async def emit(event_type: str, payload: dict) -> None:
    """Helper function to broadcast events using the singleton bus."""
    await bus.emit(event_type, payload)
