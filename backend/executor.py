"""Playbook executor (Member 2, task 2.5).

Runs an approved playbook one step at a time, in `order`, against a ClusterAdapter:

  * every action must be on the ALLOWED_ACTIONS allow-list, otherwise the step is
    blocked and the adapter is never called for it;
  * after each action the step's service is probed until healthy (or a timeout);
  * if anything goes wrong (blocked action, ok=False, adapter exception, probe
    timeout) the step is rolled back with its inverse action, the run STOPS, and
    the incident goes back to "awaiting_approval" so a human is in the loop;
  * every decision is written to an in-memory audit log (AUDIT).

`execute()` never raises to the caller and never mutates the incident it is given.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from backend.adapters.base import ALLOWED_ACTIONS, ClusterAdapter
from backend.bus import emit
from backend.models import Incident, PlaybookStep, ServiceNode, TimelineEntry

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Seconds between probe polls. Read at call time, so tests can monkeypatch it.
POLL_INTERVAL_S: float = _env_float("EXEC_POLL_S", 0.25)

DEFAULT_STEP_TIMEOUT_S: float = 30.0   # used when step.params has no timeout_s
FINAL_HEALTH_TIMEOUT_S: float = 10.0   # wait for ALL services to be healthy after the last step

# Actions whose inverse is the same action with params "from" and "to" swapped.
_SWAPPABLE_ACTIONS = {"patch_memory_limit", "patch_cpu_limit", "scale_replicas"}

# The audit log: incident id -> chronological list of entries.
AUDIT: dict[str, list[dict]] = {}


def get_audit(incident_id: str) -> list[dict]:
    """Audit entries for one incident, oldest first (a copy; safe to mutate)."""
    return [dict(entry) for entry in AUDIT.get(incident_id, [])]


def clear_audit() -> None:
    AUDIT.clear()


def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _elapsed_s(started_at: str) -> float:
    """Seconds since the incident started (t_s for timeline entries)."""
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return max(0.0, round((datetime.now(timezone.utc) - started).total_seconds(), 2))
    except Exception:
        return 0.0


def _poll_s() -> float:
    return max(POLL_INTERVAL_S, 0.001)


def _step_timeout_s(step: PlaybookStep) -> float:
    raw = (step.params or {}).get("timeout_s", DEFAULT_STEP_TIMEOUT_S)
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_STEP_TIMEOUT_S
    return timeout if timeout > 0 else DEFAULT_STEP_TIMEOUT_S


class _Run:
    """State for one execute() call. Works only on its own copy of the incident."""

    def __init__(self, incident: Incident, adapter: ClusterAdapter, approved_by: str) -> None:
        self.incident = incident
        self.adapter = adapter
        self.actor = approved_by
        self.last_status: dict[str, str] = {}   # service id -> status at the last service_update emit

    # ── small helpers ────────────────────────────────────────────────────

    def _audit(self, kind: str, **fields: Any) -> None:
        entry = {"ts": _now_z(), "incident_id": self.incident.id, "actor": self.actor, "kind": kind}
        entry.update(fields)
        AUDIT.setdefault(self.incident.id, []).append(entry)

    def _note(self, event: str) -> None:
        self.incident.timeline.append(
            TimelineEntry(t_s=_elapsed_s(self.incident.started_at), event=event)
        )

    async def _emit_incident(self) -> None:
        await emit("incident_update", self.incident)

    async def _emit_step(self, step: PlaybookStep, status: str, message: Optional[str] = None) -> None:
        payload: dict[str, Any] = {
            "incident_id": self.incident.id,
            "order": step.order,
            "service": step.service,
            "action": step.action,
            "status": status,
        }
        if message is not None:
            payload["message"] = message
        await emit("playbook_step", payload)

    @staticmethod
    def _step_fields(step: PlaybookStep) -> dict[str, Any]:
        return {"order": step.order, "service": step.service, "action": step.action, "params": step.params}

    async def _emit_changes(self, services: list[ServiceNode]) -> None:
        """service_update for every service whose status differs from the last emit."""
        for svc in services:
            if self.last_status.get(svc.id) != svc.status:
                self.last_status[svc.id] = svc.status
                await emit("service_update", svc)

    async def _sync_services(self) -> None:
        """Best-effort UI sync; a failure here must not fail the remediation."""
        try:
            await self._emit_changes(await self.adapter.list_services())
        except Exception as exc:
            logger.warning("executor: could not sync services: %s", exc)

    async def _wait_probe(self, service: str, timeout_s: float) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while True:
            if await self.adapter.probe(service):
                return True
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(_poll_s(), remaining))

    # ── the run ──────────────────────────────────────────────────────────

    async def run(self, steps: list[PlaybookStep]) -> None:
        self.incident.status = "healing"
        self._note(f"Approved by {self.actor}")
        await self._emit_incident()
        self._audit("approval")

        # Baseline for "status changed since the last emit": what the UI already shows.
        self.last_status = {s.id: s.status for s in await self.adapter.list_services()}

        for step in steps:
            if not await self._run_step(step):
                return
        await self._finish()

    async def _run_step(self, step: PlaybookStep) -> bool:
        """Runs one step. Returns True when it ran and was verified."""
        if step.action not in ALLOWED_ACTIONS:
            reason = "blocked: action not allow-listed"
            await self._emit_step(step, "failed", reason)
            self._audit("blocked", **self._step_fields(step), reason="action not allow-listed")
            await self._fail(step, reason, failed_event_sent=True, executed=False)
            return False

        await self._emit_step(step, "running")
        self._audit("action", **self._step_fields(step))

        try:
            result = await self.adapter.apply_action(step)
        except Exception as exc:
            await self._fail(step, f"adapter error: {exc}")
            return False

        await self._sync_services()

        if not result.ok:
            await self._fail(step, result.message or "action failed")
            return False

        timeout_s = _step_timeout_s(step)
        try:
            healthy = await self._wait_probe(step.service, timeout_s)
        except Exception as exc:
            await self._fail(step, f"adapter error: {exc}")
            return False
        if not healthy:
            await self._fail(step, f"verification timed out after {timeout_s:g}s")
            return False

        await self._sync_services()
        await self._emit_step(step, "done", result.message)
        self._audit("result", order=step.order, service=step.service, action=step.action,
                    ok=True, message=result.message, verified=True)
        self._note(f"Step {step.order}: {step.action} on {step.service} verified")
        return True

    async def _fail(self, step: PlaybookStep, reason: str,
                    failed_event_sent: bool = False, executed: bool = True) -> None:
        """Failure path: report, roll back this step, stop, hand back to a human."""
        if not failed_event_sent:
            await self._emit_step(step, "failed", reason)

        if executed:
            outcome = await self._rollback(step)
        else:
            outcome = "no rollback needed (action was never executed)"
        self._audit("rollback", order=step.order, service=step.service, action=step.action,
                    reason=reason, outcome=outcome)

        if executed:
            await self._sync_services()

        self.incident.status = "awaiting_approval"
        self._note(f"Step {step.order} failed, rolled back, waiting for a human")
        await self._emit_incident()

    async def _rollback(self, step: PlaybookStep) -> str:
        """Applies the inverse of `step`. Returns a human-readable outcome."""
        if step.action not in _SWAPPABLE_ACTIONS:
            return "no rollback needed"

        params = step.params or {}
        if "from" not in params or "to" not in params:
            return "rollback skipped: step params have no from/to values"

        inverse_params = dict(params)
        inverse_params["from"], inverse_params["to"] = params["to"], params["from"]
        inverse = step.model_copy(update={"params": inverse_params})
        try:
            result = await self.adapter.apply_action(inverse)
        except Exception as exc:
            return f"rollback failed: {exc}"
        if not result.ok:
            return f"rollback failed: {result.message}"
        return f"rolled back {step.action} on {step.service}: {params['to']} -> {params['from']}"

    async def _finish(self) -> None:
        """After the last step: every service must be healthy, then resolve."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + FINAL_HEALTH_TIMEOUT_S
        while True:
            services = await self.adapter.list_services()
            await self._emit_changes(services)
            unhealthy = [s.id for s in services if s.status != "healthy"]
            if not unhealthy:
                break
            remaining = deadline - loop.time()
            if remaining <= 0:
                self._audit("failure", reason="services still unhealthy after all steps", unhealthy=unhealthy)
                self.incident.status = "awaiting_approval"
                self._note("Services did not all recover, waiting for a human")
                await self._emit_incident()
                return
            await asyncio.sleep(min(_poll_s(), remaining))

        self.incident.status = "resolved"
        self.incident.resolved_at = _now_z()
        self._note("Resolved")
        await self._emit_incident()
        self._audit("resolved")


async def execute(incident: Incident, adapter: ClusterAdapter, approved_by: str) -> Incident:
    """Runs the incident's playbook. Returns an updated COPY; the input is never mutated.

    Success  -> status "resolved", resolved_at set.
    Failure  -> failed step rolled back, later steps untouched, status "awaiting_approval".
    No steps -> returned unchanged (nothing to run).
    """
    work = incident.model_copy(deep=True)
    steps = sorted(work.playbook.steps, key=lambda s: s.order) if work.playbook else []
    if not steps:
        return work

    run = _Run(work, adapter, approved_by)
    try:
        await run.run(steps)
    except Exception as exc:  # never raise to the caller
        logger.exception("executor: unexpected error")
        work.status = "awaiting_approval"
        work.timeline.append(TimelineEntry(
            t_s=_elapsed_s(work.started_at),
            event=f"Executor error ({type(exc).__name__}), waiting for a human",
        ))
        run._audit("failure", reason=f"unexpected executor error: {exc}")
        try:
            await emit("incident_update", work)
        except Exception:
            pass
    return work
