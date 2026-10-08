"""Unit tests for emit_scripted_steps and run_pipeline stub (TASK 1.9 & TASK 1.10)"""

import asyncio
import pytest
from backend.models import Incident
from backend.agents.pipeline import emit_scripted_steps, run_pipeline


class MockAdapter:
    pass


def test_emit_scripted_steps(monkeypatch):
    emitted_events = []

    async def fake_emit(event_type, payload):
        emitted_events.append((event_type, payload))

    async def fake_sleep(duration):
        pass  # Fast execution in tests

    import backend.agents.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "emit", fake_emit)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    incident = Incident(
        id="INC-104",
        status="detected",
        scenario="db_oom",
        root_service="postgres",
        impacted_services=["auth-service", "payment-service", "api-gateway", "web-ui"],
        raw_alert_count=56,
        started_at="2026-10-09T03:14:07Z",
    )

    asyncio.run(emit_scripted_steps("db_oom", incident))

    # Assert exactly 6 events emitted
    assert len(emitted_events) == 6

    # Verify event types and agents
    for ev_type, payload in emitted_events:
        assert ev_type == "agent_step"
        assert payload["agent"] in ("triage", "diagnose")

    # Step 1: triage running with raw_alert_count (56)
    assert emitted_events[0][1]["agent"] == "triage"
    assert emitted_events[0][1]["status"] == "running"
    assert "56" in emitted_events[0][1]["text"]

    # Step 2: triage done with root_service (postgres)
    assert emitted_events[1][1]["agent"] == "triage"
    assert emitted_events[1][1]["status"] == "done"
    assert "postgres" in emitted_events[1][1]["text"]

    # Step 3: diagnose running with root_service-0
    assert emitted_events[2][1]["agent"] == "diagnose"
    assert emitted_events[2][1]["status"] == "running"
    assert "postgres-0" in emitted_events[2][1]["text"]

    # Step 4: diagnose running with root_service-0
    assert emitted_events[3][1]["agent"] == "diagnose"
    assert emitted_events[3][1]["status"] == "running"
    assert "postgres-0" in emitted_events[3][1]["text"]

    # Step 5: diagnose running with memory telemetry from scenario
    assert emitted_events[4][1]["agent"] == "diagnose"
    assert emitted_events[4][1]["status"] == "running"
    assert "64" in emitted_events[4][1]["text"]

    # Step 6: diagnose done with category from cache
    assert emitted_events[5][1]["agent"] == "diagnose"
    assert emitted_events[5][1]["status"] == "done"
    assert "OOMKilled" in emitted_events[5][1]["text"]


def test_emit_scripted_steps_missing_scenario(monkeypatch):
    emitted_events = []

    async def fake_emit(event_type, payload):
        emitted_events.append((event_type, payload))

    async def fake_sleep(duration):
        pass

    import backend.agents.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "emit", fake_emit)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    incident = Incident(
        id="INC-000",
        status="detected",
        scenario="missing_scenario",
        root_service="postgres",
        impacted_services=[],
        raw_alert_count=0,
        started_at="2026-10-09T03:14:07Z",
    )

    asyncio.run(emit_scripted_steps("missing_scenario", incident))

    # Assert exactly 6 events emitted
    assert len(emitted_events) == 6

    # Verify six lines without numbers
    assert emitted_events[0][1]["text"] == "Grouping alerts using the dependency map"
    assert emitted_events[0][1]["status"] == "running"

    assert "No dependency of postgres is alerting" in emitted_events[1][1]["text"]
    assert emitted_events[1][1]["status"] == "done"

    assert emitted_events[2][1]["text"] == "Reading last 50 log lines from postgres-0"
    assert emitted_events[2][1]["status"] == "running"

    assert emitted_events[3][1]["text"] == "Reading Kubernetes events for postgres-0"
    assert emitted_events[3][1]["status"] == "running"

    assert emitted_events[4][1]["text"] == "Checking the memory trend"
    assert emitted_events[4][1]["status"] == "running"

    assert emitted_events[5][1]["text"] == "Matching the evidence"
    assert emitted_events[5][1]["status"] == "done"


def test_run_pipeline_happy_path(monkeypatch):
    emitted = []

    async def fake_emit(event_type, payload):
        emitted.append((event_type, payload))

    async def fake_sleep(duration):
        pass

    import backend.agents.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "emit", fake_emit)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    original_incident = Incident(
        id="INC-104",
        status="detected",
        scenario="db_oom",
        root_service="postgres",
        impacted_services=["auth-service", "payment-service", "api-gateway", "web-ui"],
        raw_alert_count=56,
        started_at="2026-10-09T03:14:07Z",
    )

    result_incident = asyncio.run(run_pipeline(original_incident, MockAdapter()))

    # Verify status, rca and playbook
    assert result_incident.status == "analyzing"
    assert result_incident.playbook is None
    assert result_incident.rca is not None
    assert result_incident.rca.category == "OOMKilled"

    # Original incident was not mutated
    assert original_incident.status == "detected"
    assert original_incident.rca is None


def test_run_pipeline_missing_cache(monkeypatch):
    emitted = []

    async def fake_emit(event_type, payload):
        emitted.append((event_type, payload))

    async def fake_sleep(duration):
        pass

    import backend.agents.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "emit", fake_emit)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    incident = Incident(
        id="INC-999",
        status="detected",
        scenario="non_existent_scenario",
        root_service="postgres",
        impacted_services=[],
        raw_alert_count=5,
        started_at="2026-10-09T03:14:07Z",
    )

    result = asyncio.run(run_pipeline(incident, MockAdapter()))

    # Returned incident is unchanged
    assert result.status == "detected"
    assert result.rca is None

    # Last emitted step is a failed agent_step
    last_event = emitted[-1]
    assert last_event[0] == "agent_step"
    assert last_event[1]["status"] == "failed"
    assert "No analysis available for this scenario" in last_event[1]["text"]
