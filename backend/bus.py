"""WebSocket Event Bus and Connection Manager for Agnitia."""

import asyncio
import inspect
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Set, Union
from pydantic import BaseModel

VALID_EVENT_TYPES: Set[str] = {
    "alert",
    "service_update",
    "incident_update",
    "agent_step",
    "playbook_step",
    "metric_point",
    "prediction",
    "reset",
}


def _dump_models(obj: Any) -> Any:
    """Recursively converts Pydantic models to JSON-compatible primitives."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _dump_models(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_dump_models(v) for v in obj]
    if isinstance(obj, set):
        return [_dump_models(v) for v in obj]
    return obj


class EventBus:
    """Connection manager holding active WebSocket clients and dispatching contract events."""

    def __init__(self) -> None:
        self.active_connections: Set[Any] = set()
        self._listeners: List[Callable[[Dict[str, Any]], Any]] = []

    async def connect(self, websocket: Any) -> None:
        """Accepts and stores an active WebSocket connection."""
        if hasattr(websocket, "accept"):
            await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: Any) -> None:
        """Removes a WebSocket from active connections."""
        self.active_connections.discard(websocket)

    def add_listener(self, cb: Callable[[Dict[str, Any]], Any]) -> None:
        """Registers a sync or async callback called on every emit."""
        if cb not in self._listeners:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[Dict[str, Any]], Any]) -> None:
        """Removes a registered callback listener."""
        if cb in self._listeners:
            self._listeners.remove(cb)

    async def emit(self, type: str, payload: Union[Dict[str, Any], BaseModel]) -> None:
        """
        Wraps payload in the contract envelope {"type", "ts", "payload"}
        (ts in UTC ISO-8601 ending in 'Z') and broadcasts to all active sockets using asyncio.gather.
        Drops any socket that encounters an error.
        Invokes registered listeners (sync or async) with the envelope.
        """
        if type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event type '{type}'. Valid types are: {', '.join(sorted(VALID_EVENT_TYPES))}"
            )

        # Convert Pydantic models with model_dump(mode='json')
        serialized_payload = _dump_models(payload)
        now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        envelope: Dict[str, Any] = {
            "type": type,
            "ts": now_z,
            "payload": serialized_payload,
        }

        # 1. Notify listeners (used by tests and predictor)
        for cb in list(self._listeners):
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(envelope)
                else:
                    cb(envelope)
            except Exception:
                pass

        # 2. Broadcast to connected WebSocket clients via asyncio.gather
        if self.active_connections:
            dead_sockets: Set[Any] = set()

            async def _send_to_socket(ws: Any) -> None:
                try:
                    if hasattr(ws, "send_json"):
                        await ws.send_json(envelope)
                    elif hasattr(ws, "send_text"):
                        await ws.send_text(json.dumps(envelope))
                except Exception:
                    dead_sockets.add(ws)

            await asyncio.gather(
                *[_send_to_socket(ws) for ws in list(self.active_connections)],
                return_exceptions=True,
            )

            for dead_ws in dead_sockets:
                self.disconnect(dead_ws)


bus = EventBus()
manager = bus  # Convenience alias


async def connect(ws: Any) -> None:
    await bus.connect(ws)


def disconnect(ws: Any) -> None:
    bus.disconnect(ws)


def add_listener(cb: Callable[[Dict[str, Any]], Any]) -> None:
    bus.add_listener(cb)


def remove_listener(cb: Callable[[Dict[str, Any]], Any]) -> None:
    bus.remove_listener(cb)


async def emit(type: str, payload: Union[Dict[str, Any], BaseModel]) -> None:
    await bus.emit(type, payload)
