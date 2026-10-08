"""Tests for backend/executor.py (task 2.5).

SimulatorAdapter at speed=200 on the db_oom fixture; the 5-step playbook is the one
from CONTRACT.md. The poll interval is shrunk so timeouts do not slow the suite.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
import pytest_asyncio

from backend import executor
from backend.adapters.simulator import SimulatorAdapter
from backend.bus import bus
from backend.executor import AUDIT, clear_audit, execute, get_audit
from backend.models import ActionResult, Incident, Playbook, PlaybookStep

SERVICES = ["postgres", "redis", "auth-service", "payment-service", "api-gateway", "web-ui"]


# ── Helpers ──────────────────────────────────────────────────────────────


def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _contract_steps() -> List[PlaybookStep]:
    """The 5-step db_oom playbook from CONTRACT.md section 7."""
    return [
        PlaybookStep(order=1, service="postgres", action="patch_memory_limit",
                     params={"from": "64Mi", "to": "256Mi"}, risk="high", requires_approval=True,
                     verify="port 5432 accepting connections"),
        PlaybookStep(order=2, service="postgres", action="wait_for_ready",
                     params={"timeout_s": 30}, risk="low", verify="readiness probe passes"),
        PlaybookStep(order=3, service="auth-service", action="rollout_restart",
                     risk="low", verify="health endpoint 200"),
        PlaybookStep(order=4, service="payment-service", action="rollout_restart",
                     risk="low", verify="health endpoint 200"),
        PlaybookStep(order=5, service="api-gateway", action="verify_health",
                     risk="low", verify="error rate below 1%"),
    ]


def _incident(steps: List[PlaybookStep]) -> Incident:
    return Incident(
        id="INC-104",
        status="awaiting_approval",
        scenario="db_oom",
        root_service="postgres",
        impacted_services=["auth-service", "payment-service", "api-gateway", "web-ui"],
        raw_alert_count=56,
        started_at=_now_z(),
        playbook=Playbook(diff="resources.limits.memory: 64Mi -> 256Mi", steps=steps),
    )


class SpyAdapter:
    """Delegates to a SimulatorAdapter and records every apply_action / probe call."""

    def __init__(self, inner: SimulatorAdapter) -> None:
        self.inner = inner
        self.apply_calls: List[PlaybookStep] = []
        self.probe_calls: List[str] = []
        self.probe_override: Dict[str, bool] = {}
        self.apply_error: Exception | None = None
        self.stuck_services: set = set()      # list_services reports these as "impacted" forever

    async def list_services(self):
        services = await self.inner.list_services()
        for svc in services:
            if svc.id in self.stuck_services:
                svc.status = "impacted"
        return services

    async def get_logs(self, service: str, lines: int = 50):
        return await self.inner.get_logs(service, lines)

    async def get_metrics(self, service: str):
        return await self.inner.get_metrics(service)

    async def get_events(self, service: str):
        return await self.inner.get_events(service)

    async def apply_action(self, step: PlaybookStep) -> ActionResult:
        self.apply_calls.append(step)
        if self.apply_error is not None:
            raise self.apply_error
        return await self.inner.apply_action(step)

    async def probe(self, service: str) -> bool:
        self.probe_calls.append(service)
        if service in self.probe_override:
            return self.probe_override[service]
        return await self.inner.probe(service)


@pytest_asyncio.fixture
async def env(monkeypatch):
    """(adapter, events): db_oom injected and fully played; events holds executor-time events only."""
    monkeypatch.setattr(executor, "POLL_INTERVAL_S", 0.01)
    clear_audit()
    sim = SimulatorAdapter(speed=200, step_delay_s=0.01)
    events: List[Dict[str, Any]] = []

    def listener(envelope: Dict[str, Any]) -> None:
        events.append(envelope)

    bus.add_listener(listener)
    try:
        await sim.inject("db_oom")
        for task in list(sim._running_tasks):
            await asyncio.wait_for(task, timeout=10.0)
        await asyncio.sleep(0.05)
        events.clear()
        yield SpyAdapter(sim), events
    finally:
        bus.remove_listener(listener)
        await sim.reset()
        clear_audit()


def _steps_seen(events) -> List[tuple]:
    return [(e["payload"]["order"], e["payload"]["status"]) for e in events if e["type"] == "playbook_step"]


# ── (a) happy path ───────────────────────────────────────────────────────


async def test_a_happy_path(env):
    adapter, events = env
    incident = _incident(_contract_steps())
    snapshot = incident.model_dump()

    out = await execute(incident, adapter, "aryan")

    # 5 steps, each running then done, in order 1..5
    assert _steps_seen(events) == [
        (1, "running"), (1, "done"), (2, "running"), (2, "done"), (3, "running"),
        (3, "done"), (4, "running"), (4, "done"), (5, "running"), (5, "done"),
    ]
    step_events = [e["payload"] for e in events if e["type"] == "playbook_step"]
    assert all(p["incident_id"] == "INC-104" for p in step_events)
    assert [p["service"] for p in step_events if p["status"] == "done"] == [
        "postgres", "postgres", "auth-service", "payment-service", "api-gateway"]

    # final incident
    assert out.status == "resolved"
    assert out.resolved_at is not None and out.resolved_at.endswith("Z")
    assert [t.event for t in out.timeline] == [
        "Approved by aryan",
        "Step 1: patch_memory_limit on postgres verified",
        "Step 2: wait_for_ready on postgres verified",
        "Step 3: rollout_restart on auth-service verified",
        "Step 4: rollout_restart on payment-service verified",
        "Step 5: verify_health on api-gateway verified",
        "Resolved",
    ]
    assert [t.t_s for t in out.timeline] == sorted(t.t_s for t in out.timeline)

    # the incident passed in is untouched, the returned one is a different object
    assert incident.model_dump() == snapshot
    assert out is not incident

    # incident_update: healing first, resolved last
    updates = [e["payload"] for e in events if e["type"] == "incident_update"]
    assert updates[0]["status"] == "healing" and updates[-1]["status"] == "resolved"
    assert updates[-1]["resolved_at"] == out.resolved_at

    # healing animation: postgres turns healthy between "running" and "done" of step 1
    idx_running = next(i for i, e in enumerate(events)
                       if e["type"] == "playbook_step" and e["payload"]["order"] == 1
                       and e["payload"]["status"] == "running")
    idx_done = next(i for i, e in enumerate(events)
                    if e["type"] == "playbook_step" and e["payload"]["order"] == 1
                    and e["payload"]["status"] == "done")
    assert any(e["type"] == "service_update" and e["payload"]["id"] == "postgres"
               and e["payload"]["status"] == "healthy" for e in events[idx_running:idx_done])

    # every service ends healthy; redis never changed at any point
    final: Dict[str, str] = {}
    for e in events:
        if e["type"] == "service_update":
            final[e["payload"]["id"]] = e["payload"]["status"]
    assert all(final[s] == "healthy" for s in final)
    assert {"postgres", "auth-service", "payment-service", "api-gateway", "web-ui"} <= set(final)
    assert all(e["payload"]["status"] == "healthy"
               for e in events if e["type"] == "service_update" and e["payload"]["id"] == "redis")

    # audit: approval first, one "action" entry per step (with params), resolved last
    log = get_audit("INC-104")
    assert log[0]["kind"] == "approval" and log[0]["actor"] == "aryan"
    assert log[-1]["kind"] == "resolved"
    assert all(set(("ts", "incident_id", "actor", "kind")) <= set(entry) for entry in log)
    actions = [e for e in log if e["kind"] == "action"]
    assert [(a["order"], a["service"], a["action"]) for a in actions] == [
        (1, "postgres", "patch_memory_limit"), (2, "postgres", "wait_for_ready"),
        (3, "auth-service", "rollout_restart"), (4, "payment-service", "rollout_restart"),
        (5, "api-gateway", "verify_health")]
    assert actions[0]["params"] == {"from": "64Mi", "to": "256Mi"}
    assert len([e for e in log if e["kind"] == "result"]) == 5
    assert not [e for e in log if e["kind"] in ("blocked", "rollback", "failure")]

    # the adapter saw exactly the 5 actions, nothing else
    assert [s.order for s in adapter.apply_calls] == [1, 2, 3, 4, 5]


# ── (b) misordered playbook ──────────────────────────────────────────────


async def test_b_misordered_playbook_fails_and_hands_back_to_human(env):
    adapter, events = env
    steps = _contract_steps()
    # auth-service restart BEFORE the postgres patch (short timeout keeps the test fast)
    misordered = [
        PlaybookStep(order=1, service="auth-service", action="rollout_restart",
                     params={"timeout_s": 0.3}, risk="low", verify="health endpoint 200"),
        steps[0].model_copy(update={"order": 2}),
        steps[1].model_copy(update={"order": 3}),
        steps[3].model_copy(update={"order": 4}),
        steps[4].model_copy(update={"order": 5}),
    ]
    incident = _incident(misordered)

    out = await execute(incident, adapter, "aryan")

    # step 1 fails; nothing else ran: no events, no adapter calls, no audit for steps 2..5
    assert _steps_seen(events) == [(1, "running"), (1, "failed")]
    failed = next(e["payload"] for e in events
                  if e["type"] == "playbook_step" and e["payload"]["status"] == "failed")
    assert "timed out" in failed["message"]
    assert [s.order for s in adapter.apply_calls] == [1]
    assert adapter.inner.services["postgres"].status == "root_cause"   # patch never happened

    assert out.status == "awaiting_approval"
    assert out.resolved_at is None
    assert out.timeline[-1].event == "Step 1 failed, rolled back, waiting for a human"
    updates = [e["payload"] for e in events if e["type"] == "incident_update"]
    assert updates[0]["status"] == "healing" and updates[-1]["status"] == "awaiting_approval"

    log = get_audit("INC-104")
    rollbacks = [e for e in log if e["kind"] == "rollback"]
    assert len(rollbacks) == 1
    assert rollbacks[0]["order"] == 1 and rollbacks[0]["action"] == "rollout_restart"
    assert rollbacks[0]["outcome"].startswith("no rollback needed")
    assert not [e for e in log if e.get("order", 0) >= 2]
    assert not [e for e in log if e["kind"] in ("resolved", "result")]


# ── (c) blocked action ───────────────────────────────────────────────────


async def test_c_blocked_action_never_reaches_the_adapter(env):
    adapter, events = env
    steps = [
        PlaybookStep(order=1, service="postgres", action="delete_pod", risk="high",
                     requires_approval=True, verify="pod gone"),
        _contract_steps()[0].model_copy(update={"order": 2}),
    ]
    incident = _incident(steps)

    out = await execute(incident, adapter, "aryan")

    assert adapter.apply_calls == []
    assert adapter.probe_calls == []

    # exactly one playbook_step event: failed, with the contract message, and no "running"
    step_events = [e["payload"] for e in events if e["type"] == "playbook_step"]
    assert step_events == [{
        "incident_id": "INC-104", "order": 1, "service": "postgres", "action": "delete_pod",
        "status": "failed", "message": "blocked: action not allow-listed",
    }]

    assert out.status == "awaiting_approval"
    assert out.timeline[-1].event == "Step 1 failed, rolled back, waiting for a human"
    assert adapter.inner.services["postgres"].status == "root_cause"   # nothing was touched

    log = get_audit("INC-104")
    assert [e["kind"] for e in log] == ["approval", "blocked", "rollback"]
    assert log[1]["action"] == "delete_pod"
    assert log[2]["outcome"].startswith("no rollback needed")


# ── extras: inverse rollback, exceptions, determinism ───────────────────


async def test_failed_patch_is_rolled_back_with_swapped_params(env):
    adapter, events = env
    adapter.probe_override["postgres"] = False          # the patch "applies" but never verifies
    steps = _contract_steps()
    steps[0] = steps[0].model_copy(update={"params": {"from": "64Mi", "to": "256Mi", "timeout_s": 0.2}})
    incident = _incident(steps)

    out = await execute(incident, adapter, "aryan")

    assert [(s.action, s.params["from"], s.params["to"]) for s in adapter.apply_calls] == [
        ("patch_memory_limit", "64Mi", "256Mi"),
        ("patch_memory_limit", "256Mi", "64Mi"),         # the inverse
    ]
    assert _steps_seen(events) == [(1, "running"), (1, "failed")]
    assert out.status == "awaiting_approval"
    rollback = next(e for e in get_audit("INC-104") if e["kind"] == "rollback")
    assert rollback["outcome"].startswith("rolled back")


async def test_services_that_never_recover_leave_incident_open(env, monkeypatch):
    monkeypatch.setattr(executor, "FINAL_HEALTH_TIMEOUT_S", 0.2)
    adapter, events = env
    adapter.stuck_services = {"web-ui"}                  # every step verifies, but web-ui never turns healthy
    incident = _incident(_contract_steps())

    out = await execute(incident, adapter, "aryan")

    assert [s for s in _steps_seen(events) if s[1] == "done"] == [(n, "done") for n in range(1, 6)]
    assert out.status == "awaiting_approval"
    assert out.resolved_at is None
    assert out.timeline[-1].event == "Services did not all recover, waiting for a human"
    log = get_audit("INC-104")
    failure = next(e for e in log if e["kind"] == "failure")
    assert failure["unhealthy"] == ["web-ui"]
    assert not [e for e in log if e["kind"] == "resolved"]
    assert [e["payload"]["status"] for e in events if e["type"] == "incident_update"][-1] == "awaiting_approval"


async def test_adapter_exception_never_raises(env):
    adapter, events = env
    adapter.apply_error = RuntimeError("kube-apiserver unreachable")
    incident = _incident(_contract_steps())

    out = await execute(incident, adapter, "aryan")      # must not raise

    assert out.status == "awaiting_approval"
    failed = next(e["payload"] for e in events
                  if e["type"] == "playbook_step" and e["payload"]["status"] == "failed")
    assert "kube-apiserver unreachable" in failed["message"]
    assert _steps_seen(events)[-1] == (1, "failed")
    assert any(e["kind"] == "rollback" for e in get_audit("INC-104"))


async def test_same_run_gives_same_events(monkeypatch):
    """Determinism: two identical runs produce identical events (timestamps ignored)."""
    monkeypatch.setattr(executor, "POLL_INTERVAL_S", 0.01)
    sim = SimulatorAdapter(speed=200, step_delay_s=0.01)

    def fingerprint(events):
        out = []
        for e in events:
            p = e["payload"]
            if e["type"] == "incident_update":
                out.append(("incident_update", p["status"], tuple(t["event"] for t in p["timeline"])))
            elif e["type"] == "service_update":
                out.append(("service_update", p["id"], p["status"]))
            elif e["type"] == "playbook_step":
                out.append(("playbook_step", p["order"], p["status"], p.get("message")))
        return out

    runs = []
    try:
        for _ in range(2):
            clear_audit()
            events: List[Dict[str, Any]] = []
            await sim.inject("db_oom")
            for task in list(sim._running_tasks):
                await asyncio.wait_for(task, timeout=10.0)
            await asyncio.sleep(0.05)

            def listener(envelope, _events=events):
                _events.append(envelope)

            bus.add_listener(listener)
            try:
                await execute(_incident(_contract_steps()), SpyAdapter(sim), "aryan")
            finally:
                bus.remove_listener(listener)
            audit_kinds = [(e["kind"], e.get("order")) for e in get_audit("INC-104")]
            runs.append((fingerprint(events), audit_kinds))
            await sim.reset()
    finally:
        await sim.reset()
        clear_audit()

    assert runs[0] == runs[1]
    assert len(runs[0][0]) > 10


def test_clear_audit_empties_the_log():
    AUDIT["INC-X"] = [{"kind": "approval"}]
    assert get_audit("INC-X") == [{"kind": "approval"}]
    clear_audit()
    assert AUDIT == {} and get_audit("INC-X") == []
