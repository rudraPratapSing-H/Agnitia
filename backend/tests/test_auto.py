"""Unit and integration tests for backend/ml/auto.py (Member 2, TASK P6.2)."""

import asyncio
from typing import Any, Dict, List
import pytest

from backend.ml import auto
from backend.ml import policy as P
from backend.ml.config import HOLD_AFTER_ACTION_S
from backend.models import MetricPoint, PlaybookStep, ServiceMetrics, ServiceNode


class FakeAdapter:
    """Configurable fake cluster adapter for auto-healing tests."""

    def __init__(self, probe_result: Any = True, cur_mem_mb: float = 40.0):
        self.probe_result = probe_result
        self.cur_mem_mb = cur_mem_mb
        self.applied_steps: List[PlaybookStep] = []
        self.applied_actions = self.applied_steps
        self.apply_event: asyncio.Event | None = None

    async def probe(self, service: str) -> bool:
        if isinstance(self.probe_result, list):
            return self.probe_result.pop(0) if self.probe_result else False
        if callable(self.probe_result):
            return self.probe_result(service)
        return bool(self.probe_result)

    async def apply_action(self, step: PlaybookStep) -> None:
        self.applied_steps.append(step)
        if self.apply_event is not None:
            await self.apply_event.wait()

    async def get_metrics(self, service: str):
        return [
            MetricPoint(
                t_s=0.0,
                mem_mb=self.cur_mem_mb,
                cpu_pct=20.0,
                service=service,
                mem_limit_mb=64.0,
            )
        ]

    async def list_services(self):
        return [
            ServiceNode(
                id="postgres",
                label="PostgreSQL",
                tier="data",
                depends_on=[],
                status="healthy",
                metrics=ServiceMetrics(
                    mem_mb=self.cur_mem_mb,
                    mem_limit_mb=64.0,
                    cpu_pct=20.0,
                    restarts=0,
                ),
            )
        ]


@pytest.fixture
def fake_emit():
    """Fake emit collecting (type, payload) tuples."""
    emitted = []

    async def _emit(typ: str, payload: Dict[str, Any]):
        emitted.append((typ, payload))

    _emit.events = emitted
    return _emit


@pytest.fixture
def policy_state():
    """PolicyState(level=3) pre-filled with 5 observations of 0.95 on postgres."""
    state = P.PolicyState(level=3)
    for _ in range(5):
        P.observe(state, "postgres", 0.95)
    return state


@pytest.fixture
def default_point():
    """Standard metric point for postgres with memory as dominant signal."""
    return {
        "service": "postgres",
        "mem_mb": 55,
        "mem_limit_mb": 64,
        "cpu_pct": 20,
        "restarts": 0,
        "err_pct": 0,
    }


@pytest.fixture
def default_latest():
    """Prediction probabilities after action, showing risk dropping to 0.2."""
    return {"postgres": 0.2}


@pytest.fixture
def default_ttl():
    """Default ttl_of callable."""
    return lambda s: None


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    """Patch asyncio.sleep with an async function that only yields so loop runs instantly."""
    real_sleep = asyncio.sleep

    async def _instant_sleep(secs=0):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)


@pytest.fixture(autouse=True)
def clean_auto_module():
    """Clear auto.AUDIT, _in_flight, _last_block, running tasks, and id counter before each test."""
    auto.AUDIT.clear()
    auto._in_flight.clear()
    auto._last_block.clear()
    auto._id_counter = 0
    auto._running_tasks.clear()
    yield
    auto.AUDIT.clear()
    auto._in_flight.clear()
    auto._last_block.clear()
    auto._id_counter = 0
    auto._running_tasks.clear()


# ---------------------------------------------------------------------------
# Cases (PRD six, plus three)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case_1_allowed_path(
    policy_state, default_point, default_latest, default_ttl, fake_emit
):
    """Case 1: Allowed path: events 'applied' then 'verified' in order; one audit entry with result 'healed';

    state.last_action['postgres'] == now; adapter got exactly one patch_memory_limit step with params {'from_mb':64,'to_mb':128}.
    """
    adapter = FakeAdapter(probe_result=True)
    now = 1000.0

    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=policy_state,
        now=now,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # 1. Events arrive in order 'applied' then 'verified'
    assert len(fake_emit.events) == 2
    ev_applied, ev_verified = fake_emit.events[0], fake_emit.events[1]
    assert ev_applied[0] == "healed_auto"
    assert ev_applied[1]["phase"] == "applied"
    assert ev_applied[1]["id"] == "AUTO-001"
    assert ev_applied[1]["action"] == "patch_memory_limit"
    assert ev_applied[1]["params"] == {"from_mb": 64, "to_mb": 128}

    assert ev_verified[0] == "healed_auto"
    assert ev_verified[1]["phase"] == "verified"
    assert ev_verified[1]["result"] == "healthy"
    assert ev_verified[1]["id"] == "AUTO-001"

    # 2. One audit entry with result 'healed'
    assert len(auto.AUDIT) == 1
    audit_entry = auto.AUDIT[0]
    assert audit_entry["id"] == "AUTO-001"
    assert audit_entry["result"] == "healed"
    assert audit_entry["policy"] == "auto-v1"
    assert audit_entry["service"] == "postgres"
    assert audit_entry["probability"] == 0.95
    assert audit_entry["params"] == {"from_mb": 64, "to_mb": 128}
    assert audit_entry["reasons"] == []

    # 3. state.last_action['postgres'] == now
    assert policy_state.last_action["postgres"] == now
    assert policy_state.hold_until["postgres"] == now + HOLD_AFTER_ACTION_S

    # 4. Adapter got exactly one patch_memory_limit step with params {'from_mb':64,'to_mb':128}
    assert len(adapter.applied_steps) == 1
    step = adapter.applied_steps[0]
    assert step.service == "postgres"
    assert step.action == "patch_memory_limit"
    assert step.params == {"from_mb": 64, "to_mb": 128}


@pytest.mark.asyncio
async def test_case_2_probe_false_memory_low_rolls_back(
    policy_state, default_point, default_latest, default_ttl, fake_emit
):
    """Case 2: Probe always False and memory low (20 MB):

    the inverse {'from_mb':128,'to_mb':64} is applied, event phase 'rolled_back',
    reason contains 'change undone', audit result 'rolled_back'.
    """
    adapter = FakeAdapter(probe_result=False, cur_mem_mb=20.0)
    now = 1000.0

    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=policy_state,
        now=now,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # 1. Event phase 'rolled_back', reason contains 'change undone'
    assert len(fake_emit.events) == 2
    assert fake_emit.events[0][1]["phase"] == "applied"
    assert fake_emit.events[1][0] == "healed_auto"
    assert fake_emit.events[1][1]["phase"] == "rolled_back"
    assert "change undone" in fake_emit.events[1][1]["reason"]

    # 2. Audit result 'rolled_back'
    assert len(auto.AUDIT) == 1
    assert auto.AUDIT[0]["result"] == "rolled_back"
    assert any("change undone" in r for r in auto.AUDIT[0]["reasons"])

    # 3. The inverse {'from_mb':128,'to_mb':64} is applied
    assert len(adapter.applied_steps) == 2
    assert adapter.applied_steps[0].params == {"from_mb": 64, "to_mb": 128}
    assert adapter.applied_steps[1].params == {"from_mb": 128, "to_mb": 64}


@pytest.mark.asyncio
async def test_case_3_probe_false_memory_high_keeps_limit(
    policy_state, default_point, default_latest, default_ttl, fake_emit
):
    """Case 3: Probe always False and memory 60 MB (above 0.9 of 64):

    NOT undone, the adapter got only one step, reason contains 'undoing was unsafe'.
    """
    # 60 MB > 0.9 * 64 (57.6 MB)
    adapter = FakeAdapter(probe_result=False, cur_mem_mb=60.0)
    now = 1000.0

    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=policy_state,
        now=now,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # 1. Reason contains 'undoing was unsafe'
    assert len(fake_emit.events) == 2
    assert fake_emit.events[0][1]["phase"] == "applied"
    assert fake_emit.events[1][0] == "healed_auto"
    assert fake_emit.events[1][1]["phase"] == "rolled_back"
    assert "undoing was unsafe" in fake_emit.events[1][1]["reason"]

    # 2. Audit entry says so
    assert len(auto.AUDIT) == 1
    assert auto.AUDIT[0]["result"] == "rolled_back"
    assert any("undoing was unsafe" in r for r in auto.AUDIT[0]["reasons"])

    # 3. NOT undone: adapter got only one step
    assert len(adapter.applied_steps) == 1
    assert adapter.applied_steps[0].params == {"from_mb": 64, "to_mb": 128}


@pytest.mark.asyncio
async def test_case_4_gate_blocks_cooldown_and_suppression(
    policy_state, default_point, default_latest, default_ttl, fake_emit
):
    """Case 4: Gate blocks via cooldown (pre-call policy.record_action 10 s earlier):

    one auto_blocked event whose reasons include 'R6 cooldown active';
    a second call 5 s later is suppressed;
    a call 31 s later emits again.
    """
    adapter = FakeAdapter(probe_result=True)
    now = 1000.0

    # Pre-call policy.record_action 10 s earlier
    P.record_action(policy_state, "postgres", now - 10.0, HOLD_AFTER_ACTION_S)

    # 1. First call -> one auto_blocked event with 'R6 cooldown active'
    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=policy_state,
        now=now,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    assert len(fake_emit.events) == 1
    assert fake_emit.events[0][0] == "auto_blocked"
    assert fake_emit.events[0][1]["service"] == "postgres"
    assert any("R6 cooldown active" in r for r in fake_emit.events[0][1]["reasons"])
    assert len(auto.AUDIT) == 1
    assert auto.AUDIT[0]["result"] == "blocked"

    # 2. Second call 5 s later (now + 5.0) is suppressed
    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=policy_state,
        now=now + 5.0,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    assert len(fake_emit.events) == 1
    assert len(auto.AUDIT) == 1

    # 3. A call 31 s later (now + 31.0) emits again
    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=policy_state,
        now=now + 31.0,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    assert len(fake_emit.events) == 2
    assert fake_emit.events[1][0] == "auto_blocked"
    assert len(auto.AUDIT) == 2


@pytest.mark.asyncio
async def test_case_5_kill_switch_on(
    policy_state, default_point, default_latest, default_ttl, fake_emit
):
    """Case 5: Kill switch on: nothing applied, one auto_blocked with 'R7 kill switch is on'."""
    policy_state.kill_switch = True
    adapter = FakeAdapter(probe_result=True)
    now = 1000.0

    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=policy_state,
        now=now,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # Nothing applied
    assert len(adapter.applied_steps) == 0

    # One auto_blocked with 'R7 kill switch is on'
    assert len(fake_emit.events) == 1
    assert fake_emit.events[0][0] == "auto_blocked"
    assert any("R7 kill switch is on" in r for r in fake_emit.events[0][1]["reasons"])
    assert len(auto.AUDIT) == 1
    assert auto.AUDIT[0]["result"] == "blocked"


@pytest.mark.asyncio
async def test_case_6_second_call_while_running_ignored(
    policy_state, default_point, default_latest, default_ttl, fake_emit
):
    """Case 6: Second call for the same service while the first is still running is ignored.

    (use an adapter whose apply_action waits on an asyncio.Event; assert one apply).
    """
    event = asyncio.Event()
    adapter = FakeAdapter(probe_result=True)
    adapter.apply_event = event

    # Launch call 1
    t1 = asyncio.create_task(
        auto.maybe_heal(
            service="postgres",
            prob=0.95,
            point=default_point,
            adapter=adapter,
            state=policy_state,
            now=1000.0,
            emit=fake_emit,
            latest=default_latest,
            ttl_of=default_ttl,
        )
    )

    # Yield control to let call 1 enter and pause inside apply_action
    await asyncio.sleep(0)
    assert "postgres" in auto._in_flight
    assert len(adapter.applied_steps) == 1

    # Call 2 for the same service while call 1 is running
    t2 = asyncio.create_task(
        auto.maybe_heal(
            service="postgres",
            prob=0.95,
            point=default_point,
            adapter=adapter,
            state=policy_state,
            now=1001.0,
            emit=fake_emit,
            latest=default_latest,
            ttl_of=default_ttl,
        )
    )

    await asyncio.sleep(0)
    # Call 2 must have returned immediately without doing anything
    assert t2.done()

    # Complete call 1
    event.set()
    await t1

    # Assert exactly one apply
    assert len(adapter.applied_steps) == 1
    assert "postgres" not in auto._in_flight


@pytest.mark.asyncio
async def test_case_7_g3_streak_not_full_silent(
    default_point, default_latest, default_ttl, fake_emit
):
    """Case 7: (G3) Streak not full (only two observations): no event and no audit entry."""
    state = P.PolicyState(level=3)
    # Only two observations (persistence requires 5)
    P.observe(state, "postgres", 0.95)
    P.observe(state, "postgres", 0.95)

    adapter = FakeAdapter(probe_result=True)
    now = 1000.0

    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=state,
        now=now,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # No event emitted, no audit entry logged, nothing applied
    assert len(fake_emit.events) == 0
    assert len(auto.AUDIT) == 0
    assert len(adapter.applied_steps) == 0


@pytest.mark.asyncio
async def test_case_8_reset_state_cancels_and_preserves(
    policy_state, default_point, default_latest, default_ttl, fake_emit
):
    """Case 8: reset_state() cancels an in-flight maybe_heal task and clears _in_flight and _last_block,

    but leaves AUDIT and the id counter.
    """
    # Pre-populate AUDIT and id counter and _last_block
    auto.AUDIT.append({"id": "AUTO-001", "result": "blocked"})
    auto._id_counter = 7
    auto._last_block["postgres"] = 500.0

    event = asyncio.Event()
    adapter = FakeAdapter(probe_result=True)
    adapter.apply_event = event

    # Start an in-flight maybe_heal task
    t = asyncio.create_task(
        auto.maybe_heal(
            service="postgres",
            prob=0.95,
            point=default_point,
            adapter=adapter,
            state=policy_state,
            now=1000.0,
            emit=fake_emit,
            latest=default_latest,
            ttl_of=default_ttl,
        )
    )

    await asyncio.sleep(0)
    assert "postgres" in auto._in_flight
    assert t in auto._running_tasks

    counter_before_reset = auto._id_counter
    # Call reset_state()
    auto.reset_state()
    await asyncio.sleep(0)

    # 1. Cancels the in-flight task
    assert t.cancelled() or t.done()

    # 2. Clears _running_tasks, _in_flight, and _last_block
    assert len(auto._running_tasks) == 0
    assert len(auto._in_flight) == 0
    assert len(auto._last_block) == 0

    # 3. Leaves AUDIT and the id counter (not cleared/reset)
    assert len(auto.AUDIT) == 1
    assert auto.AUDIT[0]["id"] == "AUTO-001"
    assert auto._id_counter == counter_before_reset
    assert auto._id_counter > 0


@pytest.mark.asyncio
async def test_case_9_mixed_blocked_and_healed_unique_increasing_ids(
    default_point, default_latest, default_ttl, fake_emit
):
    """Case 9: Mixed blocked and healed entries all get unique, increasing ids."""
    state = P.PolicyState(level=3)
    for _ in range(5):
        P.observe(state, "postgres", 0.95)
        P.observe(state, "auth-service", 0.95)

    adapter = FakeAdapter(probe_result=True)

    # 1. Blocked via kill switch -> produces AUTO-001
    state.kill_switch = True
    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=state,
        now=1000.0,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # 2. Healed on postgres -> produces AUTO-002
    state.kill_switch = False
    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=state,
        now=1050.0,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # 3. Blocked on postgres via cooldown -> produces AUTO-003
    await auto.maybe_heal(
        service="postgres",
        prob=0.95,
        point=default_point,
        adapter=adapter,
        state=state,
        now=1060.0,
        emit=fake_emit,
        latest=default_latest,
        ttl_of=default_ttl,
    )

    # 4. Healed on auth-service (stateless) -> produces AUTO-004
    auth_point = {
        "service": "auth-service",
        "mem_mb": 20,
        "mem_limit_mb": 64,
        "cpu_pct": 80,
        "restarts": 0,
        "err_pct": 0,
    }
    await auto.maybe_heal(
        service="auth-service",
        prob=0.95,
        point=auth_point,
        adapter=adapter,
        state=state,
        now=1100.0,
        emit=fake_emit,
        latest={"auth-service": 0.2},
        ttl_of=default_ttl,
    )

    # Verify all entries have unique, strictly increasing IDs
    assert len(auto.AUDIT) == 4
    ids = [entry["id"] for entry in auto.AUDIT]
    assert ids == ["AUTO-001", "AUTO-002", "AUTO-003", "AUTO-004"]
    assert len(set(ids)) == len(ids)

    # Verify results match sequence: blocked, healed, blocked, healed
    results = [entry["result"] for entry in auto.AUDIT]
    assert results == ["blocked", "healed", "blocked", "healed"]


# ---------------------------------------------------------------------------
# Helper / Action representation tests
# ---------------------------------------------------------------------------

def test_propose_action_and_inverse_and_to_step():
    """Unit tests for propose_action, inverse, and to_step representations."""
    # Dominant memory
    p_mem = {"mem_mb": 50.0, "mem_limit_mb": 64.0, "cpu_pct": 10.0}
    a_mem = auto.propose_action("postgres", p_mem)
    assert a_mem.name == "patch_memory_limit"
    assert a_mem.params == {"from_mb": 64, "to_mb": 128}

    inv_mem = auto.inverse(a_mem)
    assert inv_mem.name == "patch_memory_limit"
    assert inv_mem.params == {"from_mb": 128, "to_mb": 64}

    step = auto.to_step(a_mem)
    assert step.order == 1
    assert step.service == "postgres"
    assert step.action == "patch_memory_limit"
    assert step.risk == "medium"
    assert step.requires_approval is False

    # Stateless scale
    p_stateless = {"mem_mb": 10.0, "mem_limit_mb": 64.0, "cpu_pct": 80.0}
    a_scale = auto.propose_action("auth-service", p_stateless)
    assert a_scale.name == "scale_replicas"
    assert a_scale.params == {"from": 1, "to": 2}

    inv_scale = auto.inverse(a_scale)
    assert inv_scale.params == {"from": 2, "to": 1}

    # Stateful CPU
    a_cpu = auto.propose_action("postgres", p_stateless)
    assert a_cpu.name == "patch_cpu_limit"
    assert a_cpu.params == {"from_m": 500, "to_m": 1000}

    inv_cpu = auto.inverse(a_cpu)
    assert inv_cpu.params == {"from_m": 1000, "to_m": 500}
