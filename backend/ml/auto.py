"""Autonomous action, verify and rollback (Member 2, TASK P6.1)."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

try:
    from backend.ml.config import (
        HOLD_AFTER_ACTION_S,
        SAFE_TTL_S,
        SUCCESS_P,
        THRESHOLD,
        VERIFY_TIMEOUT_S,
    )
    from backend.ml import policy as P
    from backend.models import AuditEntry, PlaybookStep
except ImportError:
    from .config import (
        HOLD_AFTER_ACTION_S,
        SAFE_TTL_S,
        SUCCESS_P,
        THRESHOLD,
        VERIFY_TIMEOUT_S,
    )
    from . import policy as P
    from backend.models import AuditEntry, PlaybookStep

AUDIT: list[dict] = []        # if executor.py already keeps an audit list, append to that one instead
_in_flight: set[str] = set()
_last_block: dict[str, float] = {}
_id_counter: int = 0
_running_tasks: set[asyncio.Task] = set()


def _next_id() -> str:
    """Module counter producing AUTO-001, AUTO-002, ... without collisions (H1)."""
    global _id_counter
    _id_counter += 1
    return f"AUTO-{_id_counter:03d}"


def _log(
    service: str,
    action: Any,
    prob: float,
    result: str,
    reasons: list,
    id: Optional[str] = None,
) -> AuditEntry:
    """Build an AuditEntry, append its model_dump to AUDIT, and return it."""
    entry_id = id if id is not None else _next_id()
    now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    act_name = getattr(action, "name", str(action))
    act_params = getattr(action, "params", {})
    entry = AuditEntry(
        id=entry_id,
        ts=now_z,
        policy="auto-v1",
        service=service,
        action=act_name,
        params=act_params,
        probability=round(prob, 3),
        result=result,
        reasons=list(reasons),
    )
    AUDIT.append(entry.model_dump())
    return entry


def reset_state() -> None:
    """Cancel running maybe_heal tasks, clear in-flight and last_block (H2/H3). Preserves AUDIT and id counter."""
    for t in list(_running_tasks):
        t.cancel()
    _running_tasks.clear()
    _in_flight.clear()
    _last_block.clear()


def propose_action(service: str, point: Any) -> P.Action:
    """One reversible fix, chosen from the dominant signal."""
    mem_mb = point["mem_mb"] if isinstance(point, dict) else getattr(point, "mem_mb")
    mem_limit_mb = point["mem_limit_mb"] if isinstance(point, dict) else getattr(point, "mem_limit_mb")
    cpu_pct = point["cpu_pct"] if isinstance(point, dict) else getattr(point, "cpu_pct")
    mem, cpu = float(mem_mb) / float(mem_limit_mb), float(cpu_pct) / 100.0
    if mem >= cpu:
        lim = int(mem_limit_mb)
        return P.Action("patch_memory_limit", service, {"from_mb": lim, "to_mb": lim * 2})
    if service in P.STATELESS:
        return P.Action("scale_replicas", service, {"from": 1, "to": 2})
    return P.Action("patch_cpu_limit", service, {"from_m": 500, "to_m": 1000})


def inverse(a: P.Action) -> Optional[P.Action]:
    p = a.params
    if a.name == "patch_memory_limit":
        return P.Action(a.name, a.service, {"from_mb": p["to_mb"], "to_mb": p["from_mb"]})
    if a.name == "patch_cpu_limit":
        return P.Action(a.name, a.service, {"from_m": p["to_m"], "to_m": p["from_m"]})
    if a.name == "scale_replicas":
        return P.Action(a.name, a.service, {"from": p["to"], "to": p["from"]})
    return None  # a restart cannot be undone


def to_step(a: P.Action) -> PlaybookStep:
    return PlaybookStep(
        order=1,
        service=a.service,
        action=a.name,
        params=a.params,
        risk="medium",
        requires_approval=False,
        verify="health check passes",
    )


async def _verified(adapter: Any, service: str, latest: Dict[str, float], ttl_of: Any) -> bool:
    for _ in range(VERIFY_TIMEOUT_S):
        await asyncio.sleep(1)
        ttl = ttl_of(service)
        if await adapter.probe(service) and (latest.get(service, 1.0) < SUCCESS_P or (ttl is not None and ttl > SAFE_TTL_S)):
            return True
    return False


async def _try_undo(adapter: Any, action: P.Action) -> bool:
    inv = inverse(action)
    if inv is None:
        return False
    if action.name == "patch_memory_limit":  # lowering a limit below current use would kill the service
        metrics = await adapter.get_metrics(action.service)
        if not metrics:  # no data to judge safety by -- assume unsafe to undo
            return False
        cur = metrics[-1]
        cur_mem = cur.mem_mb if hasattr(cur, "mem_mb") else cur["mem_mb"]
        if cur_mem > 0.9 * action.params["from_mb"]:
            return False
    await adapter.apply_action(to_step(inv))
    return True


async def maybe_heal(
    service: str,
    prob: float,
    point: Any,
    adapter: Any,
    state: P.PolicyState,
    now: float,
    emit: Any,
    latest: Dict[str, float],
    ttl_of: Any,
) -> None:
    task = asyncio.current_task()
    if task is not None:
        _running_tasks.add(task)
    try:
        if prob < THRESHOLD or service in _in_flight:
            return
        action = propose_action(service, point)
        d = P.decide(state, action, now)
        if not d.allowed:
            # PRD-gap G3, confirm with Member 3
            if d.reasons and all(r.startswith("R1/R2") for r in d.reasons):
                return
            if now - _last_block.get(service, -1e9) > 30:  # at most one notice per 30 s
                _last_block[service] = now
                await emit("auto_blocked", {"service": service, "probability": round(prob, 3), "reasons": d.reasons})
                _log(service, action, prob, "blocked", d.reasons)
            return
        _in_flight.add(service)
        try:
            base = {
                "id": _next_id(),
                "service": service,
                "action": action.name,
                "params": action.params,
                "probability": round(prob, 3),
                "policy": "auto-v1",
            }
            P.record_action(state, service, now, HOLD_AFTER_ACTION_S)
            await emit("healed_auto", {**base, "phase": "applied"})
            await adapter.apply_action(to_step(action))
            if await _verified(adapter, service, latest, ttl_of):
                await emit("healed_auto", {**base, "phase": "verified", "result": "healthy"})
                _log(service, action, prob, "healed", [], base["id"])
            else:
                undone = await _try_undo(adapter, action)
                why = "health check failed or risk stayed high; " + (
                    "change undone" if undone else "kept the new limit because undoing was unsafe"
                )
                await emit("healed_auto", {**base, "phase": "rolled_back", "reason": why})
                _log(service, action, prob, "rolled_back", [why], base["id"])
        finally:
            _in_flight.discard(service)
    finally:
        if task is not None:
            _running_tasks.discard(task)
