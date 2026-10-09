"""Tests for Predictive Auto-Heal in backend/main.py (PRD Task P6.4)."""

import asyncio
import time
from typing import Any, Dict, List
import pytest
from httpx import ASGITransport, AsyncClient

from backend.bus import bus
import backend.main as main
from backend.main import _StubPredictor, app, adapter, policy_state
from backend.ml import auto, policy as P


@pytest.mark.asyncio
async def test_flag_off_ml_status_disabled_and_old_flow_unchanged(monkeypatch):
    """Flag off -> /api/ml/status enabled false and the old flow unchanged."""
    monkeypatch.setenv("PREDICTIVE_HEAL", "off")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check /api/ml/status
        resp = await client.get("/api/ml/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["model_loaded"] is False
        assert "threshold" in data
        assert "kill_switch" in data
        assert "level" in data

        # Check old flow unchanged (db_oom inject & reset)
        chaos_resp = await client.post("/api/chaos/db_oom")
        assert chaos_resp.status_code == 200
        assert chaos_resp.json() == {"ok": True, "scenario": "db_oom"}

        reset_resp = await client.post("/api/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_debug_route_404_with_debug_0(monkeypatch):
    """Debug route returns 404 with DEBUG=0, and 409 if predictor is None."""
    monkeypatch.setenv("DEBUG", "0")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/debug/prediction", json={"service": "postgres", "p": 0.95})
        assert resp.status_code == 404

        # With DEBUG=1 but predictor is None -> 409
        monkeypatch.setenv("DEBUG", "1")
        monkeypatch.setattr(main, "predictor", None)
        resp_409 = await client.post("/api/debug/prediction", json={"service": "postgres", "p": 0.95})
        assert resp_409.status_code == 409


@pytest.mark.asyncio
async def test_autonomy_clamps_to_1_to_3():
    """Autonomy clamps input level to 1..3."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Clamp low
        r0 = await client.post("/api/autonomy", json={"level": 0})
        assert r0.status_code == 200
        assert r0.json() == {"level": 1}
        assert main.policy_state.level == 1

        # Clamp high
        r9 = await client.post("/api/autonomy", json={"level": 9})
        assert r9.status_code == 200
        assert r9.json() == {"level": 3}
        assert main.policy_state.level == 3

        # Middle
        r2 = await client.post("/api/autonomy", json={"level": 2})
        assert r2.status_code == 200
        assert r2.json() == {"level": 2}
        assert main.policy_state.level == 2


@pytest.mark.asyncio
async def test_audit_since_returns_only_later_entries():
    """/api/audit?since=AUTO-001 returns only later entries."""
    auto.AUDIT.clear()
    auto.AUDIT.extend([
        {"id": "AUTO-001", "service": "postgres", "action": "patch_memory_limit", "probability": 0.95, "result": "healed"},
        {"id": "AUTO-002", "service": "redis", "action": "patch_memory_limit", "probability": 0.91, "result": "healed"},
        {"id": "AUTO-003", "service": "postgres", "action": "patch_memory_limit", "probability": 0.93, "result": "healed"},
    ])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Since AUTO-001 -> returns AUTO-002 and AUTO-003
        r1 = await client.get("/api/audit?since=AUTO-001")
        assert r1.status_code == 200
        items1 = r1.json()
        assert len(items1) == 2
        assert [item["id"] for item in items1] == ["AUTO-002", "AUTO-003"]

        # Since AUTO-002 -> returns AUTO-003
        r2 = await client.get("/api/audit?since=AUTO-002")
        assert r2.status_code == 200
        items2 = r2.json()
        assert len(items2) == 1
        assert items2[0]["id"] == "AUTO-003"

        # Since AUTO-003 -> returns empty
        r3 = await client.get("/api/audit?since=AUTO-003")
        assert r3.status_code == 200
        assert r3.json() == []

        # Unknown id -> returns all
        r_all = await client.get("/api/audit?since=AUTO-999")
        assert r_all.status_code == 200
        assert len(r_all.json()) == 3


@pytest.mark.asyncio
async def test_debug_stub_predictor_five_posts_applied_and_verified(monkeypatch):
    """
    With the stub predictor and DEBUG=1, five posts of p=0.95 yield 'applied'
    and one audit entry once verification passes (post p=0.1 afterwards).
    """
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("PREDICTIVE_HEAL", "on")

    stub = _StubPredictor()
    monkeypatch.setattr(main, "predictor", stub)

    # Autonomy level 3 allows unapproved remediation
    main.policy_state.level = 3
    main.policy_state.kill_switch = False
    main.policy_state.reset()
    auto.reset_state()
    auto.AUDIT.clear()

    # Track emitted events
    emitted: List[Dict[str, Any]] = []

    def _bus_spy(envelope: Dict[str, Any]):
        emitted.append(envelope)

    bus.add_listener(_bus_spy)

    # Patch asyncio.sleep so tests run fast (yield instead of sleeping seconds)
    orig_sleep = asyncio.sleep

    async def _fast_sleep(s=0):
        await orig_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(auto.asyncio, "sleep", _fast_sleep)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Four posts of p=0.95 -> streak builds, nothing applied yet
        for _ in range(4):
            resp = await client.post("/api/debug/prediction", json={"service": "postgres", "p": 0.95})
            assert resp.status_code == 200

        applied_events = [
            e for e in emitted
            if e.get("type") == "healed_auto" and e.get("payload", {}).get("phase") == "applied"
        ]
        assert len(applied_events) == 0

        # Fifth post of p=0.95 -> passes persistence threshold, triggers heal
        resp5 = await client.post("/api/debug/prediction", json={"service": "postgres", "p": 0.95})
        assert resp5.status_code == 200

        # Yield to let maybe_heal spawn and reach _verified
        for _ in range(5):
            await orig_sleep(0)

        applied_events = [
            e for e in emitted
            if e.get("type") == "healed_auto" and e.get("payload", {}).get("phase") == "applied"
        ]
        assert len(applied_events) == 1
        assert applied_events[0]["payload"]["service"] == "postgres"

        # Now post p=0.1 to satisfy the verification condition (latest < SUCCESS_P 0.5)
        resp_low = await client.post("/api/debug/prediction", json={"service": "postgres", "p": 0.1})
        assert resp_low.status_code == 200

        # Yield to allow _verified to detect p < 0.5 and emit verified
        for _ in range(10):
            await orig_sleep(0)

        verified_events = [
            e for e in emitted
            if e.get("type") == "healed_auto" and e.get("payload", {}).get("phase") == "verified"
        ]
        assert len(verified_events) == 1
        assert verified_events[0]["payload"]["result"] == "healthy"

        # One audit entry with result "healed"
        assert len(auto.AUDIT) == 1
        assert auto.AUDIT[0]["result"] == "healed"
        assert auto.AUDIT[0]["service"] == "postgres"

    bus.remove_listener(_bus_spy)


@pytest.mark.asyncio
async def test_killswitch_on_blocks_with_r7_and_nothing_applied(monkeypatch):
    """Kill switch on -> auto_blocked with R7 and nothing applied."""
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("PREDICTIVE_HEAL", "on")

    stub = _StubPredictor()
    monkeypatch.setattr(main, "predictor", stub)

    main.policy_state.level = 3
    main.policy_state.reset()
    auto.reset_state()
    auto.AUDIT.clear()

    emitted: List[Dict[str, Any]] = []

    def _bus_spy(envelope: Dict[str, Any]):
        emitted.append(envelope)

    bus.add_listener(_bus_spy)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Turn kill switch ON via POST /api/killswitch
        ks_resp = await client.post("/api/killswitch", json={"on": True})
        assert ks_resp.status_code == 200
        assert ks_resp.json() == {"kill_switch": True}
        assert main.policy_state.kill_switch is True

        # Check agent_step emitted
        ks_step = [
            e for e in emitted
            if e.get("type") == "agent_step" and "Kill switch ON" in e.get("payload", {}).get("text", "")
        ]
        assert len(ks_step) == 1

        # Post 5 times p=0.95
        for _ in range(5):
            resp = await client.post("/api/debug/prediction", json={"service": "postgres", "p": 0.95})
            assert resp.status_code == 200

        # Yield to let background heal_task execute
        for _ in range(5):
            await asyncio.sleep(0)

        # Check auto_blocked was emitted with R7 reason
        blocked_events = [
            e for e in emitted
            if e.get("type") == "auto_blocked"
        ]
        assert len(blocked_events) == 1
        reasons = blocked_events[0]["payload"]["reasons"]
        assert any("R7" in r for r in reasons)

        # Nothing was applied
        applied_events = [
            e for e in emitted
            if e.get("type") == "healed_auto"
        ]
        assert len(applied_events) == 0

        # Audit contains one blocked entry
        assert len(auto.AUDIT) == 1
        assert auto.AUDIT[0]["result"] == "blocked"

    bus.remove_listener(_bus_spy)


@pytest.mark.asyncio
async def test_reset_path_completes_in_under_2_seconds():
    """Reset path: emit 'reset' calls predictor.reset(), policy_state.reset(), and auto.reset_state(). Completes < 2s."""
    stub = _StubPredictor()
    stub.hist["postgres"].append({"t_s": 1.0, "mem_mb": 50.0})
    stub.latest["postgres"] = 0.95
    main.predictor = stub

    P.observe(main.policy_state, "postgres", 0.95)
    assert len(main.policy_state.probs) > 0

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_t = time.monotonic()
        resp = await client.post("/api/reset")
        duration = time.monotonic() - start_t

        assert resp.status_code == 200
        assert duration < 2.0, f"Reset took {duration}s, must be < 2s"

        # Give asyncio tasks a tick
        await asyncio.sleep(0.01)

        # Verify state is cleared
        assert len(stub.hist) == 0
        assert len(stub.latest) == 0
        assert len(main.policy_state.probs) == 0
