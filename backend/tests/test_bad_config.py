"""
Test suite for bad_config scenario (Task 1.12 - Member 4)
Verifies:
1. bad_config.json passes validation
2. Alert count is exactly 31 with breakdown 8/14/9
3. Unaffected services (auth-service, postgres, redis) stay healthy
4. Simulator plays it end-to-end:
   - inject("bad_config") emits exactly 31 alerts
   - payment-service becomes root_cause, api-gateway & web-ui become impacted
   - rollback_deployment heals payment-service and cascades to heal dependents
"""

import asyncio
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List
import pytest

from backend.adapters.simulator import SimulatorAdapter
from backend.bus import bus
from backend.models import PlaybookStep
from backend.scenarios.validate import validate_scenario


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = REPO_ROOT / "backend" / "scenarios"
BAD_CONFIG_PATH = SCENARIOS_DIR / "bad_config.json"


def test_validate_bad_config_passes():
    ok, counts, data = validate_scenario(BAD_CONFIG_PATH)
    assert ok is True
    assert counts["payment-service"] == 8
    assert counts["api-gateway"] == 14
    assert counts["web-ui"] == 9
    assert sum(counts.values()) == 31
    assert data["fix"]["action"] == "rollback_deployment"
    assert data["fix"]["to"] == "payment-service:rev-6"


@pytest.mark.asyncio
async def test_simulator_plays_bad_config_end_to_end():
    adapter = SimulatorAdapter(speed=200, step_delay_s=0.01)
    events: List[Dict[str, Any]] = []

    def listener(envelope: Dict[str, Any]) -> None:
        events.append(envelope)

    bus.add_listener(listener)

    try:
        # 1. Inject bad_config scenario
        incident_id = await adapter.inject("bad_config")
        assert incident_id == "INC-104"

        # Wait for playback to finish
        for task in list(adapter._running_tasks):
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        await asyncio.sleep(0.05)

        # 2. Verify alert count and breakdown
        alert_events = [e for e in events if e["type"] == "alert"]
        assert len(alert_events) == 31, f"Expected 31 alerts, got {len(alert_events)}"

        alert_ids = [e["payload"]["id"] for e in alert_events]
        expected_ids = [f"a-{i:03d}" for i in range(1, 32)]
        assert alert_ids == expected_ids

        counts = Counter(e["payload"]["service"] for e in alert_events)
        assert counts["payment-service"] == 8
        assert counts["api-gateway"] == 14
        assert counts["web-ui"] == 9

        # Unaffected services have 0 alerts
        assert "auth-service" not in counts
        assert "postgres" not in counts
        assert "redis" not in counts

        # 3. Check service states during active incident
        services = {s.id: s for s in await adapter.list_services()}
        assert services["payment-service"].status == "root_cause"
        assert services["api-gateway"].status == "impacted"
        assert services["web-ui"].status == "impacted"
        assert services["auth-service"].status == "healthy"
        assert services["postgres"].status == "healthy"
        assert services["redis"].status == "healthy"

        # 4. Apply remediation fix: rollback_deployment on payment-service
        fix_step = PlaybookStep(
            order=1,
            service="payment-service",
            action="rollback_deployment",
            params={"from": "payment-service:rev-7", "to": "payment-service:rev-6"},
            risk="low",
            requires_approval=True,
            verify="payment-service pods in 1/1 Running state",
        )
        result = await adapter.apply_action(fix_step)
        assert result.ok is True
        assert "Fix applied" in result.message

        # 5. Check healed state: all services should be healthy
        services_healed = {s.id: s for s in await adapter.list_services()}
        for svc_id, svc in services_healed.items():
            assert svc.status == "healthy", f"Service {svc_id} expected healthy, got {svc.status}"

        # Probes all return True
        for svc_id in services_healed:
            assert await adapter.probe(svc_id) is True

    finally:
        bus.remove_listener(listener)
        await adapter.reset()
