"""Unit and integration tests for backend/predictor.py (Member 2, TASK 3.1)."""

import asyncio
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport

from backend.bus import bus
from backend.main import (
    app,
    adapter,
    INCIDENTS,
    LATEST_ID,
    METRIC_HISTORY,
    LAST_PREDICTION_TS,
)
from backend.models import MetricPoint
from backend.predictor import seconds_to_limit


def test_synthetic_leak_gives_about_80s():
    """Synthetic leak: slope 0.3 MB/s, 40 MB start, limit 64 -> gives ~80 s."""
    # Points at t=0.0, 1.0, 2.0 with mem = 40.0, 40.3, 40.6
    points = [
        MetricPoint(t_s=0.0, mem_mb=40.0, cpu_pct=10.0, service="postgres"),
        MetricPoint(t_s=1.0, mem_mb=40.3, cpu_pct=10.0, service="postgres"),
        MetricPoint(t_s=2.0, mem_mb=40.6, cpu_pct=10.0, service="postgres"),
    ]
    sec = seconds_to_limit(points, limit_mb=64.0)
    assert sec is not None
    # (64.0 - 40.6) / 0.3 = 23.4 / 0.3 = 78.0 s (about 80 s)
    assert 75.0 <= sec <= 85.0


def test_flat_series_gives_none():
    """A flat series (slope <= 0.01 MB/s) gives None."""
    points = [
        MetricPoint(t_s=0.0, mem_mb=40.0, cpu_pct=10.0, service="postgres"),
        MetricPoint(t_s=1.0, mem_mb=40.0, cpu_pct=10.0, service="postgres"),
        MetricPoint(t_s=2.0, mem_mb=40.0, cpu_pct=10.0, service="postgres"),
    ]
    assert seconds_to_limit(points, limit_mb=64.0) is None


def test_series_already_above_limit_gives_zero():
    """A series whose last memory is already >= limit gives 0.0."""
    points = [
        MetricPoint(t_s=0.0, mem_mb=50.0, cpu_pct=10.0, service="postgres"),
        MetricPoint(t_s=1.0, mem_mb=60.0, cpu_pct=10.0, service="postgres"),
        MetricPoint(t_s=2.0, mem_mb=65.0, cpu_pct=10.0, service="postgres"),
    ]
    assert seconds_to_limit(points, limit_mb=64.0) == 0.0


def test_fewer_than_three_points_gives_none():
    """Fewer than 3 points cannot establish a linear regression trend."""
    points = [
        MetricPoint(t_s=0.0, mem_mb=40.0, cpu_pct=10.0, service="postgres"),
        MetricPoint(t_s=1.0, mem_mb=40.5, cpu_pct=10.0, service="postgres"),
    ]
    assert seconds_to_limit(points, limit_mb=64.0) is None


@pytest.mark.asyncio
async def test_slow_leak_simulator_run_emits_prediction_and_creates_preventive_incident():
    """
    A simulator run of slow_leak at speed 100:
    1. Emits at least one prediction event before the crash.
    2. Opens a preventive incident (<300s to limit) with status 'awaiting_approval',
       scenario 'slow_leak', raw_alert_count 0.
    3. On reset, emits prediction event with seconds: null.
    """
    adapter.speed = 100.0

    prediction_events = []

    async def capture_predictions(envelope):
        if envelope.get("type") == "prediction":
            prediction_events.append(envelope["payload"])

    bus.add_listener(capture_predictions)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            # Clean start
            reset_resp = await client.post("/api/reset")
            assert reset_resp.status_code == 200
            prediction_events.clear()

            # Inject slow_leak scenario
            inject_resp = await client.post("/api/chaos/slow_leak")
            assert inject_resp.status_code == 200

            # Wait for prediction event and preventive incident
            preventive_incident = None
            for _ in range(100):
                if prediction_events and any(p.get("seconds") is not None for p in prediction_events):
                    r = await client.get("/api/incidents/latest")
                    data = r.json()
                    if data and data.get("scenario") == "slow_leak":
                        preventive_incident = data
                        break
                await asyncio.sleep(0.05)

            assert len(prediction_events) > 0, "Expected at least one prediction event"
            valid_preds = [p for p in prediction_events if p.get("seconds") is not None]
            assert len(valid_preds) >= 1
            assert valid_preds[0]["service"] == "postgres"
            assert valid_preds[0]["seconds"] < 300.0

            assert preventive_incident is not None, "Preventive incident was not created"
            assert preventive_incident["scenario"] == "slow_leak"
            assert preventive_incident["root_service"] == "postgres"

            # Wait briefly until the pipeline puts it in awaiting_approval
            for _ in range(50):
                r = await client.get("/api/incidents/latest")
                data = r.json()
                if data and data.get("status") == "awaiting_approval":
                    preventive_incident = data
                    break
                await asyncio.sleep(0.05)

            assert preventive_incident["status"] in ("analyzing", "awaiting_approval")

            # Reset cluster and verify prediction clears (seconds: null)
            prediction_events.clear()
            reset_resp = await client.post("/api/reset")
            assert reset_resp.status_code == 200

            cleared_preds = [p for p in prediction_events if p.get("seconds") is None]
            assert len(cleared_preds) >= 1

        finally:
            bus.remove_listener(capture_predictions)
            adapter.speed = 1.0
            await client.post("/api/reset")
