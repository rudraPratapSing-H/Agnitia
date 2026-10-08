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
def ensure_sim_speed(monkeypatch):
    adapter.speed = 200.0
    orig_sleep = asyncio.sleep
    async def fast_sleep(s, *args, **kwargs):
        return await orig_sleep(s / 200.0, *args, **kwargs)
    try:
        import backend.agents.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod.asyncio, "sleep", fast_sleep)
    except Exception:
        pass
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
            ("GET", "/api/incidents/INC-104/postmortem"),
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
async def test_approval_execution_and_audit_flow():
    """
    TASK 2.6 Full flow:
    Inject -> wait for awaiting_approval -> approve -> poll until resolved -> audit non-empty.
    Second approve -> 409.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/reset")

        # 1. Inject
        resp = await client.post("/api/chaos/db_oom")
        assert resp.status_code == 200

        # 2. Wait for awaiting_approval
        incident_id = None
        for _ in range(100):
            r = await client.get("/api/incidents/latest")
            data = r.json()
            if data and data.get("status") == "awaiting_approval":
                incident_id = data["id"]
                break
            await asyncio.sleep(0.05)

        assert incident_id is not None, "Timed out waiting for awaiting_approval"

        # 3. Approve
        approve_resp = await client.post(
            f"/api/incidents/{incident_id}/approve",
            json={"approved_by": "telegram:alice"},
        )
        assert approve_resp.status_code == 202
        assert approve_resp.json() == {"ok": True, "status": "healing"}

        # 4. Immediate second approve -> 409
        second_approve = await client.post(
            f"/api/incidents/{incident_id}/approve",
            json={"approved_by": "telegram:alice"},
        )
        assert second_approve.status_code == 409
        assert "awaiting_approval" in second_approve.json()["detail"].lower()

        # 5. Poll until resolved
        resolved_inc = None
        for _ in range(120):
            r = await client.get("/api/incidents/latest")
            data = r.json()
            if data and data.get("status") == "resolved":
                resolved_inc = data
                break
            await asyncio.sleep(0.05)

        assert resolved_inc is not None, "Timed out waiting for incident resolved"
        assert resolved_inc["resolved_at"] is not None
        assert any("Approved by telegram:alice" in t["event"] for t in resolved_inc["timeline"])
        assert any("Resolved" in t["event"] for t in resolved_inc["timeline"])

        # 6. Audit non-empty
        audit_resp = await client.get(f"/api/incidents/{incident_id}/audit")
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()
        assert isinstance(audit_data, list)
        assert len(audit_data) > 0
        assert audit_data[0]["kind"] == "approval"
        assert audit_data[0]["actor"] == "telegram:alice"
        assert audit_data[-1]["kind"] == "resolved"

        # Clean up
        await client.post("/api/reset")


@pytest.mark.asyncio
async def test_unknown_id_approve_reject_audit_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post("/api/incidents/INC-UNKNOWN/approve")
        assert resp1.status_code == 404

        resp2 = await client.post("/api/incidents/INC-UNKNOWN/reject")
        assert resp2.status_code == 404

        resp3 = await client.get("/api/incidents/INC-UNKNOWN/audit")
        assert resp3.status_code == 404


@pytest.mark.asyncio
async def test_reject_path():
    """
    Reject flow:
    Inject -> wait for awaiting_approval -> reject -> status becomes 'detected', playbook None.
    Second reject -> 409.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/reset")

        await client.post("/api/chaos/db_oom")

        incident_id = None
        for _ in range(100):
            r = await client.get("/api/incidents/latest")
            data = r.json()
            if data and data.get("status") == "awaiting_approval":
                incident_id = data["id"]
                break
            await asyncio.sleep(0.05)

        assert incident_id is not None

        # Reject
        reject_resp = await client.post(
            f"/api/incidents/{incident_id}/reject",
            json={"rejected_by": "lead-sre"},
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json() == {"ok": True}

        # Check latest
        latest_resp = await client.get("/api/incidents/latest")
        data = latest_resp.json()
        assert data["status"] == "detected"
        assert data["playbook"] is None
        assert any("Playbook rejected by lead-sre" in t["event"] for t in data["timeline"])

        # Second reject -> 409
        second_reject = await client.post(
            f"/api/incidents/{incident_id}/reject",
            json={"rejected_by": "lead-sre"},
        )
        assert second_reject.status_code == 409

        await client.post("/api/reset")


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


@pytest.mark.asyncio
async def test_blast_radius_endpoint():
    """TASK 2.7: GET /api/blast-radius/{service} tests:
    - redis -> affected_services == ['auth-service', 'api-gateway', 'web-ui']
    - web-ui -> []
    - unknown -> 404
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. redis
        resp_redis = await client.get("/api/blast-radius/redis")
        assert resp_redis.status_code == 200
        data_redis = resp_redis.json()
        assert data_redis["service"] == "redis"
        assert data_redis["affected_services"] == ["auth-service", "api-gateway", "web-ui"]
        assert data_redis["users_affected_pct"] == 70
        assert data_redis["note"] == "illustrative simulator figure"

        # 2. web-ui
        resp_web = await client.get("/api/blast-radius/web-ui")
        assert resp_web.status_code == 200
        data_web = resp_web.json()
        assert data_web["service"] == "web-ui"
        assert data_web["affected_services"] == []
        assert data_web["users_affected_pct"] == 100
        assert data_web["note"] == "illustrative simulator figure"

        # 3. postgres
        resp_pg = await client.get("/api/blast-radius/postgres")
        assert resp_pg.status_code == 200
        data_pg = resp_pg.json()
        assert data_pg["service"] == "postgres"
        assert data_pg["affected_services"] == [
            "auth-service",
            "payment-service",
            "api-gateway",
            "web-ui",
        ]
        assert data_pg["users_affected_pct"] == 100

        # 4. unknown -> 404
        resp_unknown = await client.get("/api/blast-radius/unknown-service")
        assert resp_unknown.status_code == 404

