"""Tests for backend/main.py REST endpoints and WebSocket stream."""

import asyncio
import os
from typing import Any, Dict, List
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient

# Ensure SIM_SPEED=200 for fast deterministic simulation
os.environ["SIM_SPEED"] = "200"

import backend.main as main_module
from backend.main import (
    app,
    adapter,
    INCIDENTS,
    LATEST_ID,
    init_adapter,
    on_alerts_complete,
)
from backend.models import Alert


@pytest.fixture(autouse=True)
def ensure_sim_speed():
    adapter.speed = 200.0
    yield
    adapter.speed = 200.0


@pytest.mark.asyncio
async def test_chaos_lifecycle_and_invariants():
    """
    PRD verification flow:
    1. Inject db_oom -> 200 {"ok": True, "scenario": "db_oom"}
    2. Poll /api/incidents/latest until status == 'awaiting_approval'
    3. Verify raw_alert_count == 56, root == 'postgres', 4 impacted
    4. Reset -> latest is null and all 6 services healthy
    5. Second inject while running -> 409
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Clean slate
        reset_resp = await client.post("/api/reset")
        assert reset_resp.status_code == 200

        # 1. Inject db_oom
        inject_resp = await client.post("/api/chaos/db_oom")
        assert inject_resp.status_code == 200
        assert inject_resp.json() == {"ok": True, "scenario": "db_oom"}

        # 2. Poll /api/incidents/latest until status == "awaiting_approval"
        incident_data = None
        for _ in range(100):  # poll up to 5 seconds
            latest_resp = await client.get("/api/incidents/latest")
            assert latest_resp.status_code == 200
            data = latest_resp.json()
            if data and data.get("status") == "awaiting_approval":
                incident_data = data
                break
            await asyncio.sleep(0.05)

        assert incident_data is not None, "Timed out waiting for incident status awaiting_approval"

        # 3. Assertions on Incident
        assert incident_data["raw_alert_count"] == 56
        assert incident_data["root_service"] == "postgres"
        assert len(incident_data["impacted_services"]) == 4
        assert set(incident_data["impacted_services"]) == {
            "auth-service",
            "payment-service",
            "api-gateway",
            "web-ui",
        }
        assert incident_data["scenario"] == "db_oom"
        assert len(incident_data["timeline"]) >= 2
        assert incident_data["timeline"][0]["event"] == "First alert received"
        assert "Alerts correlated into" in incident_data["timeline"][1]["event"]

        # 4. Reset -> latest is null and all services healthy
        reset_resp = await client.post("/api/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json() == {"ok": True}

        latest_after_reset = await client.get("/api/incidents/latest")
        assert latest_after_reset.status_code == 200
        assert latest_after_reset.json() is None  # JSON null

        # Verify all services healthy via adapter
        services = await adapter.list_services()
        assert len(services) == 6
        for svc in services:
            assert svc.status == "healthy"

        # Verify all services healthy via /api/services
        services_resp = await client.get("/api/services")
        assert services_resp.status_code == 200
        for s in services_resp.json():
            assert s["status"] == "healthy"

        # 5. Second inject while running -> 409
        # Run at normal speed so scenario stays playing during second call
        adapter.speed = 1.0
        first_inject = await client.post("/api/chaos/db_oom")
        assert first_inject.status_code == 200

        second_inject = await client.post("/api/chaos/db_oom")
        assert second_inject.status_code == 409
        assert "already playing" in second_inject.json()["detail"].lower()

        # Clean up
        adapter.speed = 200.0
        await client.post("/api/reset")


@pytest.mark.asyncio
async def test_unknown_scenario_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chaos/unknown_scenario")
        assert resp.status_code == 404
        assert "unknown" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_placeholder_endpoints_return_501():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        endpoints = [
            ("POST", "/api/incidents/INC-104/approve"),
            ("POST", "/api/incidents/INC-104/reject"),
            ("GET", "/api/incidents/INC-104/postmortem"),
            ("GET", "/api/blast-radius/postgres"),
            ("GET", "/api/incidents/INC-104/audit"),
            ("GET", "/api/audit"),
            ("POST", "/api/autonomy"),
        ]
        for method, path in endpoints:
            if method == "POST":
                resp = await client.post(path)
            else:
                resp = await client.get(path)
            assert resp.status_code == 501, f"{method} {path} should return 501"
            assert resp.json() == {"detail": "not implemented yet"}


@pytest.mark.asyncio
async def test_pipeline_fallback_stub_when_pipeline_missing(monkeypatch):
    """When run_pipeline is None, fallback stub sets status 'awaiting_approval'."""
    monkeypatch.setattr(main_module, "run_pipeline", None)

    fake_alerts = [
        Alert(
            id="a-001",
            ts="2026-10-09T03:00:00Z",
            service="postgres",
            severity="critical",
            message="OOM killed",
            incident_id="INC-999",
        )
    ]

    await on_alerts_complete("db_oom", fake_alerts)

    assert main_module.LATEST_ID == "INC-999"
    incident = main_module.INCIDENTS["INC-999"]
    assert incident.status == "awaiting_approval"
    assert incident.root_service == "postgres"

    # Reset
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/reset")


@pytest.mark.asyncio
async def test_pipeline_exception_handling(monkeypatch):
    """When pipeline raises, status stays 'analyzing' and error is logged."""
    async def failing_pipeline(inc, adp):
        raise RuntimeError("LLM synthesis timeout")

    monkeypatch.setattr(main_module, "run_pipeline", failing_pipeline)

    fake_alerts = [
        Alert(
            id="a-002",
            ts="2026-10-09T03:00:00Z",
            service="postgres",
            severity="critical",
            message="OOM killed",
            incident_id="INC-888",
        )
    ]

    await on_alerts_complete("db_oom", fake_alerts)

    assert main_module.LATEST_ID == "INC-888"
    incident = main_module.INCIDENTS["INC-888"]
    assert incident.status == "analyzing"

    # Reset
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/reset")


def test_websocket_connect_and_state_recovery():
    """WS /ws immediately sends service_update per service and incident_update if present."""
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        # First 6 messages should be service_update
        received_services = []
        for _ in range(6):
            data = ws.receive_json()
            assert data["type"] == "service_update"
            received_services.append(data["payload"]["id"])

        assert len(received_services) == 6
        assert "postgres" in received_services
        assert "web-ui" in received_services
