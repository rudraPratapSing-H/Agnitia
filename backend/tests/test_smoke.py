"""Unit tests for demo/smoke.py (TASK SMOKE / Member 2)."""

import argparse
import asyncio
import json
from unittest.mock import patch
import pytest

from demo.smoke import (
    main_async,
    run_single_predictive_leak,
    run_single_predictive_harmless,
)


class MockWebSocket:
    """Mock WebSocket that yields pre-defined messages."""
    def __init__(self, messages):
        self.messages = list(messages)
        self.idx = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def recv(self):
        if self.idx < len(self.messages):
            msg = self.messages[self.idx]
            self.idx += 1
            await asyncio.sleep(0.01)
            return json.dumps(msg)
        while True:
            await asyncio.sleep(0.1)


class MockHttpClient:
    """Mock HTTP client for reset and chaos injection."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def post(self, url, **kwargs):
        class Resp:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"ok": True}
        return Resp()

    async def get(self, url, **kwargs):
        class Resp:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"ok": True}
        return Resp()


@pytest.mark.asyncio
async def test_predictive_leak_happy_path(monkeypatch):
    """Leak run happy path: sees prediction, applied, verified, respects window."""
    events = [
        {"type": "prediction", "payload": {"service": "postgres", "probability": 0.88}},
        {"type": "healed_auto", "payload": {"service": "postgres", "phase": "applied", "probability": 0.95}},
        {"type": "healed_auto", "payload": {"service": "postgres", "phase": "verified", "result": "healthy"}},
    ]

    monkeypatch.setattr("websockets.connect", lambda *args, **kwargs: MockWebSocket(events))
    client = MockHttpClient()

    passed, apply_time, apply_prob, msg = await run_single_predictive_leak(
        run_idx=1,
        base_url="http://test",
        ws_url="ws://test/ws",
        client=client,
        window=(0.0, 10.0),
    )

    assert passed is True
    assert apply_time is not None
    assert 0.0 <= apply_time <= 10.0
    assert apply_prob == 0.95
    assert msg == "OK"


@pytest.mark.asyncio
async def test_predictive_leak_rolled_back_fails(monkeypatch):
    """Leak run where rolled_back event is received fails assertion."""
    events = [
        {"type": "healed_auto", "payload": {"service": "postgres", "phase": "applied", "probability": 0.95}},
        {"type": "healed_auto", "payload": {"service": "postgres", "phase": "rolled_back", "reason": "probe failed"}},
    ]

    monkeypatch.setattr("websockets.connect", lambda *args, **kwargs: MockWebSocket(events))
    client = MockHttpClient()

    passed, apply_time, apply_prob, msg = await run_single_predictive_leak(
        run_idx=1,
        base_url="http://test",
        ws_url="ws://test/ws",
        client=client,
    )

    assert passed is False
    assert "rolled_back" in msg


@pytest.mark.asyncio
async def test_predictive_leak_root_cause_fails(monkeypatch):
    """Leak run where postgres reaches root_cause fails assertion."""
    events = [
        {"type": "service_update", "payload": {"id": "postgres", "status": "root_cause"}},
    ]

    monkeypatch.setattr("websockets.connect", lambda *args, **kwargs: MockWebSocket(events))
    client = MockHttpClient()

    passed, apply_time, apply_prob, msg = await run_single_predictive_leak(
        run_idx=1,
        base_url="http://test",
        ws_url="ws://test/ws",
        client=client,
    )

    assert passed is False
    assert "root_cause" in msg


@pytest.mark.asyncio
async def test_predictive_leak_window_mismatch_fails(monkeypatch):
    """Leak run with applied time outside specified window fails."""
    events = [
        {"type": "healed_auto", "payload": {"service": "postgres", "phase": "applied", "probability": 0.95}},
        {"type": "healed_auto", "payload": {"service": "postgres", "phase": "verified", "result": "healthy"}},
    ]

    monkeypatch.setattr("websockets.connect", lambda *args, **kwargs: MockWebSocket(events))
    client = MockHttpClient()

    # Window [50.0, 60.0] will not match immediate mock (< 1.0s)
    passed, apply_time, apply_prob, msg = await run_single_predictive_leak(
        run_idx=1,
        base_url="http://test",
        ws_url="ws://test/ws",
        client=client,
        window=(50.0, 60.0),
    )

    assert passed is False
    assert "outside window" in msg


@pytest.mark.asyncio
async def test_predictive_harmless_happy_path(monkeypatch):
    """Harmless run with ZERO healed_auto and ZERO auto_blocked passes."""
    events = [
        {"type": "metric_point", "payload": {"service": "postgres", "mem_mb": 42.0}},
    ]

    monkeypatch.setenv("SIM_SPEED", "2000.0")  # 310 / 2000 = ~0.155s watch time
    monkeypatch.setattr("websockets.connect", lambda *args, **kwargs: MockWebSocket(events))
    client = MockHttpClient()

    passed, apply_time, apply_prob, msg = await run_single_predictive_harmless(
        scenario="healthy_spike",
        run_idx=1,
        base_url="http://test",
        ws_url="ws://test/ws",
        client=client,
    )

    assert passed is True
    assert apply_time is None
    assert apply_prob is None
    assert msg == "OK"


@pytest.mark.asyncio
async def test_predictive_harmless_unexpected_healed_fails(monkeypatch):
    """Harmless run fails if healed_auto event occurs."""
    events = [
        {"type": "healed_auto", "payload": {"phase": "applied"}},
    ]

    monkeypatch.setenv("SIM_SPEED", "2000.0")
    monkeypatch.setattr("websockets.connect", lambda *args, **kwargs: MockWebSocket(events))
    client = MockHttpClient()

    passed, apply_time, apply_prob, msg = await run_single_predictive_harmless(
        scenario="healthy_spike",
        run_idx=1,
        base_url="http://test",
        ws_url="ws://test/ws",
        client=client,
    )

    assert passed is False
    assert "healed_auto" in msg


@pytest.mark.asyncio
async def test_predictive_harmless_unexpected_blocked_fails(monkeypatch):
    """Harmless run fails if auto_blocked event occurs."""
    events = [
        {"type": "auto_blocked", "payload": {"reasons": ["R6 cooldown"]}},
    ]

    monkeypatch.setenv("SIM_SPEED", "2000.0")
    monkeypatch.setattr("websockets.connect", lambda *args, **kwargs: MockWebSocket(events))
    client = MockHttpClient()

    passed, apply_time, apply_prob, msg = await run_single_predictive_harmless(
        scenario="sawtooth",
        run_idx=1,
        base_url="http://test",
        ws_url="ws://test/ws",
        client=client,
    )

    assert passed is False
    assert "auto_blocked" in msg


@pytest.mark.asyncio
async def test_main_async_predictive_orchestration(monkeypatch):
    """main_async with --predictive and mock runs returns exit code 0."""
    monkeypatch.setattr("demo.smoke.httpx.AsyncClient", lambda *args, **kwargs: MockHttpClient())

    async def fake_leak(*args, **kwargs):
        return True, 52.0, 0.95, "OK"

    async def fake_harmless(*args, **kwargs):
        return True, None, None, "OK"

    monkeypatch.setattr("demo.smoke.run_single_predictive_leak", fake_leak)
    monkeypatch.setattr("demo.smoke.run_single_predictive_harmless", fake_harmless)

    args = argparse.Namespace(
        predictive=True,
        runs=1,
        only=None,
        window=None,
        base="http://test",
    )

    exit_code = await main_async(args)
    assert exit_code == 0
