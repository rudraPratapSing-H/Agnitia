"""Unit tests for Diagnose Agent (no network, monkeypatched LLM)"""

import asyncio
from backend.models import RCA, LogLine, MetricPoint, K8sEvent
from backend.agents.diagnose import diagnose, downsample_metrics


def test_diagnose_payload_and_return_rca(monkeypatch):
    captured_payload = {}

    # Dummy RCA response for monkeypatched call_json
    fake_rca = RCA(
        root_cause="PostgreSQL out of memory crash",
        category="OOMKilled",
        confidence=0.98,
        evidence=[],
    )

    async def fake_call_json(system_prompt, payload, model_cls, *, timeout_s=4.0):
        nonlocal captured_payload
        captured_payload = payload
        return fake_rca

    from backend.agents import llm
    monkeypatch.setattr(llm, "call_json", fake_call_json)

    # Generate 70 log lines (more than 50 to test truncation to last 50)
    logs = [
        LogLine(line=i, t_s=float(i), text=f"Log statement #{i}")
        for i in range(1, 71)
    ]

    events = [
        K8sEvent(t_s=60.0, service="postgres", text="Reason: OOMKilled, Exit Code: 137")
    ]

    # Generate 60 metric points (more than 40 to test downsampling)
    metrics = [
        MetricPoint(t_s=float(i), mem_mb=20.0 + (i * 0.5), cpu_pct=10.0)
        for i in range(1, 61)
    ]
    # Inject a distinct maximum
    metrics[25].mem_mb = 120.0

    async def _run():
        return await diagnose("postgres", logs, events, metrics)

    result = asyncio.run(_run())

    # 1. Assert returns an RCA
    assert isinstance(result, RCA)
    assert result.root_cause == "PostgreSQL out of memory crash"

    # 2. Assert payload contains the last 50 log lines with line numbers
    payload_logs = captured_payload["logs"]
    assert len(payload_logs) == 50
    assert payload_logs[0]["line"] == 21  # 70 - 50 + 1
    assert payload_logs[-1]["line"] == 70

    # 3. Assert downsampling keeps at most 40 points, preserves the last point and maximum
    payload_metrics = captured_payload["metrics"]
    assert len(payload_metrics) <= 40
    # Last point must be preserved (t_s = 60.0)
    assert payload_metrics[-1]["t_s"] == 60.0
    # Maximum point must be preserved (mem_mb = 120.0)
    assert any(m["mem_mb"] == 120.0 for m in payload_metrics)


def test_downsample_metrics_logic():
    points = [
        MetricPoint(t_s=float(i), mem_mb=float(i), cpu_pct=5.0)
        for i in range(100)
    ]
    downsampled = downsample_metrics(points, max_points=40)
    assert len(downsampled) <= 40
    # Last point preserved
    assert downsampled[-1].t_s == 99.0
    # Max point preserved
    assert downsampled[-1].mem_mb == 99.0
