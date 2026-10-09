"""Integration and unit tests for backend/main.py routes (Member 2, TASK 1.3)."""

import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app, adapter


@pytest.fixture(autouse=True)
def setup_simulator_speed(monkeypatch):
    """Ensure adapter and pipeline run fast for tests."""
    monkeypatch.setenv("DEMO_MODE", "cache")
    try:
        import backend.agents.pipeline as pipeline
        monkeypatch.setattr(pipeline, "STEP_PACE_S", (0.0, 0.0))
    except Exception:
        pass
    if adapter is not None:
        adapter.speed = 200.0
        adapter.step_delay_s = 0.01
    yield
    if adapter is not None:
        adapter.speed = 1.0
        adapter.step_delay_s = 2.0




@pytest.mark.asyncio
async def test_health():
    """GET /api/health returns {'ok': True}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_inject_db_oom_and_poll_incident():
    """
    Inject db_oom at speed=200 -> poll /api/incidents/latest until status 'awaiting_approval'.
    Verify raw_alert_count 56, root postgres, 4 impacted.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Reset first
        await client.post("/api/reset")

        # Inject db_oom
        inject_resp = await client.post("/api/chaos/db_oom")
        assert inject_resp.status_code == 200
        assert inject_resp.json() == {"ok": True, "scenario": "db_oom"}

        # Poll /api/incidents/latest until awaiting_approval
        incident = None
        for _ in range(80):
            r = await client.get("/api/incidents/latest")
            assert r.status_code == 200
            data = r.json()
            if data and data.get("status") == "awaiting_approval":
                incident = data
                break
            await asyncio.sleep(0.05)

        assert incident is not None, "Timed out waiting for incident in status 'awaiting_approval'"
        assert incident["scenario"] == "db_oom"
        assert incident["root_service"] == "postgres"
        assert incident["raw_alert_count"] == 56
        assert len(incident["impacted_services"]) == 4
        assert set(incident["impacted_services"]) == {
            "auth-service",
            "payment-service",
            "api-gateway",
            "web-ui",
        }
        assert "redis" not in incident["impacted_services"]

        # Clean reset at end
        await client.post("/api/reset")


@pytest.mark.asyncio
async def test_reset_restores_null_incident_and_healthy_services():
    """Reset -> /api/incidents/latest returns null and all services become healthy."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Inject to produce incident
        await client.post("/api/chaos/db_oom")
        # Wait a moment
        await asyncio.sleep(0.1)

        # Reset
        reset_resp = await client.post("/api/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json() == {"ok": True}

        # Verify /api/incidents/latest is JSON null
        latest_resp = await client.get("/api/incidents/latest")
        assert latest_resp.status_code == 200
        assert latest_resp.json() is None

        # Verify all services in adapter are healthy
        services = await adapter.list_services()
        assert all(s.status == "healthy" for s in services)


@pytest.mark.asyncio
async def test_second_inject_while_running_raises_409():
    """Second inject while already running returns 409 Conflict."""
    if adapter is not None:
        adapter.speed = 1.0  # Slow speed so it is guaranteed to be running

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/reset")

        r1 = await client.post("/api/chaos/db_oom")
        assert r1.status_code == 200

        # Second inject immediately
        r2 = await client.post("/api/chaos/db_oom")
        assert r2.status_code == 409

        await client.post("/api/reset")


@pytest.mark.asyncio
async def test_unknown_scenario_returns_404():
    """Injecting unknown scenario returns 404 Not Found."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chaos/unknown_flavor")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_placeholders_return_501():
    """Endpoints planned for future tasks return 501 Not Implemented."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/incidents/INC-104/approve")).status_code == 501
        assert (await client.post("/api/incidents/INC-104/reject")).status_code == 501
        assert (await client.get("/api/incidents/INC-104/postmortem")).status_code == 501
        assert (await client.get("/api/blast-radius/postgres")).status_code == 501
        assert (await client.get("/api/incidents/INC-104/audit")).status_code == 501


def test_websocket_stream_initial_updates():
    """WS /ws immediately sends service_update per service on connect."""
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        client.post("/api/reset")
        with client.websocket_connect("/ws") as ws:
            received = [ws.receive_json() for _ in range(6)]
            assert all(msg["type"] == "service_update" for msg in received)
            services = {msg["payload"]["id"] for msg in received}
            assert len(services) == 6
            assert "postgres" in services
            assert "redis" in services

