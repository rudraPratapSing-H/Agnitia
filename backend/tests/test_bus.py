"""Unit tests for backend/bus.py (WebSocket Event Bus)."""

import pytest
from pydantic import BaseModel
from backend.bus import (
    bus,
    emit,
    connect,
    disconnect,
    add_listener,
    remove_listener,
    VALID_EVENT_TYPES,
)


class MockPydanticModel(BaseModel):
    name: str
    count: int


class MockWebSocket:
    def __init__(self, should_fail: bool = False):
        self.accepted = False
        self.sent_messages = []
        self.should_fail = should_fail

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        if self.should_fail:
            raise ConnectionResetError("Connection lost")
        self.sent_messages.append(data)


@pytest.fixture(autouse=True)
def clean_bus():
    """Ensure bus state is reset between tests."""
    orig_listeners = list(bus._listeners)
    bus.active_connections.clear()
    bus._listeners.clear()
    yield
    bus.active_connections.clear()
    bus._listeners = orig_listeners


@pytest.mark.asyncio
async def test_invalid_event_type_raises_value_error():
    with pytest.raises(ValueError, match="Invalid event type 'invalid_type'"):
        await emit("invalid_type", {"test": True})


@pytest.mark.asyncio
async def test_all_valid_event_types_accepted():
    captured = []
    add_listener(lambda env: captured.append(env))

    for event_type in VALID_EVENT_TYPES:
        await emit(event_type, {"event": event_type})

    assert len(captured) == len(VALID_EVENT_TYPES)
    types_seen = {env["type"] for env in captured}
    assert types_seen == VALID_EVENT_TYPES


@pytest.mark.asyncio
async def test_envelope_structure_and_ts_format():
    captured = []
    add_listener(lambda env: captured.append(env))

    await emit("alert", {"id": "alt-01", "service": "postgres"})

    assert len(captured) == 1
    envelope = captured[0]
    assert envelope["type"] == "alert"
    assert envelope["payload"] == {"id": "alt-01", "service": "postgres"}

    # Timestamp must be UTC ISO-8601 ending in "Z"
    ts = envelope["ts"]
    assert isinstance(ts, str)
    assert ts.endswith("Z")
    assert "T" in ts


@pytest.mark.asyncio
async def test_pydantic_model_serialization():
    captured = []
    add_listener(lambda env: captured.append(env))

    model = MockPydanticModel(name="test_service", count=42)

    # 1. Direct model as payload
    await emit("service_update", model)
    assert captured[-1]["payload"] == {"name": "test_service", "count": 42}

    # 2. Nested model inside dict
    await emit("service_update", {"nested": model, "other": "val"})
    assert captured[-1]["payload"] == {
        "nested": {"name": "test_service", "count": 42},
        "other": "val",
    }


@pytest.mark.asyncio
async def test_sync_and_async_listeners():
    sync_called = []
    async_called = []

    def sync_cb(env):
        sync_called.append(env["type"])

    async def async_cb(env):
        async_called.append(env["type"])

    add_listener(sync_cb)
    add_listener(async_cb)

    await emit("reset", {})

    assert sync_called == ["reset"]
    assert async_called == ["reset"]

    # Test listener removal
    remove_listener(sync_cb)
    remove_listener(async_cb)

    await emit("reset", {})
    assert len(sync_called) == 1
    assert len(async_called) == 1


@pytest.mark.asyncio
async def test_zero_clients_works_without_error():
    assert len(bus.active_connections) == 0
    # Must execute smoothly without error
    await emit("metric_point", {"t_s": 1.0, "mem_mb": 50.0})


@pytest.mark.asyncio
async def test_websocket_broadcast_and_failing_socket_dropped():
    ws_good = MockWebSocket(should_fail=False)
    ws_bad = MockWebSocket(should_fail=True)

    await connect(ws_good)
    await connect(ws_bad)

    assert ws_good.accepted is True
    assert ws_bad.accepted is True
    assert len(bus.active_connections) == 2

    await emit("prediction", {"seconds": 45.0})

    # Good socket received the message
    assert len(ws_good.sent_messages) == 1
    assert ws_good.sent_messages[0]["type"] == "prediction"

    # Failing socket must have been removed from active connections
    assert ws_bad not in bus.active_connections
    assert ws_good in bus.active_connections
    assert len(bus.active_connections) == 1
