"""Unit tests for backend/adapters/simulator.py.

All tests run at speed=200 with a bus listener to capture emitted events.
Uses the fixture file backend/tests/fixtures/db_oom_fixture.json.
"""

import asyncio
from collections import Counter
from typing import Any, Dict, List

import pytest

from backend.adapters.simulator import SimulatorAdapter
from backend.bus import bus
from backend.models import PlaybookStep


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_adapter() -> SimulatorAdapter:
    """Creates a fast adapter for testing."""
    return SimulatorAdapter(speed=200, step_delay_s=0.01)


def _collector() -> tuple:
    """Returns (events_list, listener_function)."""
    events: List[Dict[str, Any]] = []

    def listener(envelope: Dict[str, Any]) -> None:
        events.append(envelope)

    return events, listener


async def _inject_and_wait(adapter: SimulatorAdapter) -> str:
    """Injects db_oom and waits for playback to finish."""
    incident_id = await adapter.inject("db_oom")
    # Wait for the playback task(s) to complete
    for task in list(adapter._running_tasks):
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    # Small extra sleep for on_alerts_complete task
    await asyncio.sleep(0.05)
    return incident_id


def _fix_step() -> PlaybookStep:
    return PlaybookStep(
        order=1,
        service="postgres",
        action="patch_memory_limit",
        params={"from": "64Mi", "to": "256Mi"},
        risk="high",
        requires_approval=True,
        verify="port 5432 accepting connections",
    )


def _restart_step(service: str, order: int = 2) -> PlaybookStep:
    return PlaybookStep(
        order=order,
        service=service,
        action="rollout_restart",
        risk="low",
        requires_approval=False,
        verify=f"health endpoint 200 for {service}",
    )


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_exactly_56_alerts_correct_ids_and_counts():
    """(a) exactly 56 alert events, ids a-001..a-056, per-service counts 1/10/15/18/12, none for redis."""
    adapter = _make_adapter()
    events, listener = _collector()
    bus.add_listener(listener)

    try:
        await _inject_and_wait(adapter)

        alert_events = [e for e in events if e["type"] == "alert"]
        assert len(alert_events) == 56, f"Expected 56 alerts, got {len(alert_events)}"

        # IDs a-001 to a-056 in order
        alert_ids = [e["payload"]["id"] for e in alert_events]
        expected_ids = [f"a-{i:03d}" for i in range(1, 57)]
        assert alert_ids == expected_ids

        # Per-service counts
        counts = Counter(e["payload"]["service"] for e in alert_events)
        assert counts["postgres"] == 1
        assert counts["auth-service"] == 10
        assert counts["payment-service"] == 15
        assert counts["api-gateway"] == 18
        assert counts["web-ui"] == 12
        assert "redis" not in counts

        # All alerts carry the incident_id
        for e in alert_events:
            assert e["payload"]["incident_id"] == "INC-104"
    finally:
        bus.remove_listener(listener)
        await adapter.reset()


@pytest.mark.asyncio
async def test_b_on_alerts_complete_called_once():
    """(b) on_alerts_complete called once with 56 alerts."""
    adapter = _make_adapter()
    events, listener = _collector()
    bus.add_listener(listener)

    calls: List[tuple] = []

    async def on_complete(scenario_id: str, alerts: list) -> None:
        calls.append((scenario_id, len(alerts)))

    adapter.on_alerts_complete = on_complete

    try:
        await _inject_and_wait(adapter)

        assert len(calls) == 1
        assert calls[0][0] == "db_oom"
        assert calls[0][1] == 56
    finally:
        bus.remove_listener(listener)
        await adapter.reset()


@pytest.mark.asyncio
async def test_c_statuses_after_run():
    """(c) after the run: postgres root_cause, 4 impacted, redis healthy."""
    adapter = _make_adapter()
    events, listener = _collector()
    bus.add_listener(listener)

    try:
        await _inject_and_wait(adapter)

        assert adapter.services["postgres"].status == "root_cause"
        assert adapter.services["auth-service"].status == "impacted"
        assert adapter.services["payment-service"].status == "impacted"
        assert adapter.services["api-gateway"].status == "impacted"
        assert adapter.services["web-ui"].status == "impacted"
        assert adapter.services["redis"].status == "healthy"
    finally:
        bus.remove_listener(listener)
        await adapter.reset()


@pytest.mark.asyncio
async def test_d_probe_and_fix_sequence():
    """(d) probe(postgres) False; applying the fix step then probe(postgres) True;
    rollout_restart auth-service BEFORE the fix leaves probe(auth-service) False;
    after the fix plus restarts of auth-service and payment-service,
    api-gateway and web-ui probe True.
    """
    adapter = _make_adapter()
    events, listener = _collector()
    bus.add_listener(listener)

    try:
        await _inject_and_wait(adapter)

        # Before fix: postgres not healthy
        assert await adapter.probe("postgres") is False

        # Restart auth-service BEFORE fix: should NOT become healthy
        result = await adapter.apply_action(_restart_step("auth-service", order=1))
        assert result.ok is True
        assert await adapter.probe("auth-service") is False

        # Apply the fix to postgres
        result = await adapter.apply_action(_fix_step())
        assert result.ok is True
        assert await adapter.probe("postgres") is True

        # auth-service still not healthy (restarted before fix, deps weren't healthy)
        assert await adapter.probe("auth-service") is False

        # Now restart auth-service (postgres is healthy)
        result = await adapter.apply_action(_restart_step("auth-service", order=3))
        assert result.ok is True
        assert await adapter.probe("auth-service") is True

        # Restart payment-service
        result = await adapter.apply_action(_restart_step("payment-service", order=4))
        assert result.ok is True
        assert await adapter.probe("payment-service") is True

        # api-gateway and web-ui should now be healthy (all deps are healthy, auto-propagation)
        assert await adapter.probe("api-gateway") is True
        assert await adapter.probe("web-ui") is True
    finally:
        bus.remove_listener(listener)
        await adapter.reset()


@pytest.mark.asyncio
async def test_e_determinism():
    """(e) determinism: run twice with reset between; the event sequences
    (type, service, alert id/message, ignoring ts) are identical.
    """
    adapter = _make_adapter()

    def extract_fingerprint(events_list: List[Dict[str, Any]]) -> List[tuple]:
        """Extract deterministic fingerprint ignoring timestamps."""
        fingerprint = []
        for e in events_list:
            etype = e["type"]
            payload = e["payload"]
            if etype == "alert":
                fingerprint.append((etype, payload.get("service"), payload.get("id"), payload.get("message")))
            elif etype == "metric_point":
                fingerprint.append((etype, payload.get("service"), payload.get("t_s"), payload.get("mem_mb")))
            elif etype == "service_update":
                fingerprint.append((etype, payload.get("id"), payload.get("status")))
            else:
                fingerprint.append((etype,))
        return fingerprint

    # Run 1
    events1, listener1 = _collector()
    bus.add_listener(listener1)
    await _inject_and_wait(adapter)
    bus.remove_listener(listener1)
    fp1 = extract_fingerprint(events1)

    await adapter.reset()

    # Run 2
    events2, listener2 = _collector()
    bus.add_listener(listener2)
    await _inject_and_wait(adapter)
    bus.remove_listener(listener2)
    fp2 = extract_fingerprint(events2)

    await adapter.reset()

    assert fp1 == fp2, "Event sequences differ between runs"
    assert len(fp1) > 0


@pytest.mark.asyncio
async def test_f_reset_restores_everything():
    """(f) reset restores everything healthy and the next incident id is INC-104 again."""
    adapter = _make_adapter()
    events, listener = _collector()
    bus.add_listener(listener)

    try:
        await _inject_and_wait(adapter)

        # postgres should be root_cause
        assert adapter.services["postgres"].status == "root_cause"

        await adapter.reset()

        # All services healthy
        for svc in adapter.services.values():
            assert svc.status == "healthy", f"{svc.id} should be healthy after reset"

        # Incident counter reset
        assert adapter._incident_counter == 104

        # No scenario active
        assert adapter._scenario is None

        # Can inject again with same INC-104
        incident_id = await adapter.inject("db_oom")
        assert incident_id == "INC-104"

        # Wait for it
        for task in list(adapter._running_tasks):
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    finally:
        bus.remove_listener(listener)
        await adapter.reset()


@pytest.mark.asyncio
async def test_inject_unknown_scenario_raises_value_error():
    """Unknown scenario id raises ValueError."""
    adapter = _make_adapter()
    with pytest.raises(ValueError, match="Unknown scenario"):
        await adapter.inject("nonexistent_scenario")
    await adapter.reset()


@pytest.mark.asyncio
async def test_inject_while_running_raises_runtime_error():
    """Injecting while a scenario is already running raises RuntimeError."""
    adapter = _make_adapter()
    await adapter.inject("db_oom")
    with pytest.raises(RuntimeError, match="already running"):
        await adapter.inject("db_oom")

    # Clean up
    await adapter.reset()


@pytest.mark.asyncio
async def test_disallowed_action_returns_not_ok():
    """Action not in ALLOWED_ACTIONS returns ok=False."""
    adapter = _make_adapter()
    step = PlaybookStep(
        order=1,
        service="postgres",
        action="delete_pod",
        risk="high",
        requires_approval=True,
        verify="should fail",
    )
    result = await adapter.apply_action(step)
    assert result.ok is False
    assert "ALLOWED_ACTIONS" in result.message
    await adapter.reset()
