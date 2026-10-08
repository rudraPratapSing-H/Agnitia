"""Deterministic Cluster Simulator implementing ClusterAdapter.

Plays a scenario file from backend/scenarios/<id>.json on a timeline.
All timing goes through self._sleep(s) = asyncio.sleep(s / speed) so tests
can run at speed=200.
"""

import asyncio
import copy
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from backend.adapters.base import ALLOWED_ACTIONS
from backend.bus import emit
from backend.graph import DEPENDS_ON, TIERS, SERVICE_LABELS, find_root
from backend.models import (
    ActionResult,
    Alert,
    K8sEvent,
    LogLine,
    MetricPoint,
    PlaybookStep,
    ServiceMetrics,
    ServiceNode,
)

logger = logging.getLogger(__name__)

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"

# Default memory limits per service
_DEFAULT_MEM_LIMITS: Dict[str, float] = {
    "postgres": 64.0,
    "redis": 64.0,
    "auth-service": 128.0,
    "payment-service": 128.0,
    "api-gateway": 128.0,
    "web-ui": 128.0,
}

# Default baseline metrics per service
_DEFAULT_METRICS: Dict[str, Dict[str, float]] = {
    "postgres": {"mem_mb": 40.0, "cpu_pct": 12.0},
    "redis": {"mem_mb": 24.0, "cpu_pct": 3.0},
    "auth-service": {"mem_mb": 50.0, "cpu_pct": 8.0},
    "payment-service": {"mem_mb": 72.0, "cpu_pct": 11.0},
    "api-gateway": {"mem_mb": 65.0, "cpu_pct": 14.0},
    "web-ui": {"mem_mb": 42.0, "cpu_pct": 5.0},
}

class SimulatorAdapter(ClusterAdapter):
    def __init__(self):
        self.services: Dict[str, ServiceNode] = {}
        self.active_scenario: Optional[dict] = None
        self.logs_store: Dict[str, List[LogLine]] = {svc: [] for svc in DEFAULT_SERVICES}
        self.metrics_store: Dict[str, List[MetricPoint]] = {svc: [] for svc in DEFAULT_SERVICES}
        self.events_store: Dict[str, List[K8sEvent]] = {svc: [] for svc in DEFAULT_SERVICES}
        self.reset()

    def reset(self):
        """Resets all monitored services to healthy status and clears active incidents."""
        self.services = {
            s_id: ServiceNode(
                id=s_id,
                label=data["label"],
                tier=data["tier"],
                depends_on=data["depends_on"],
                status="healthy",
                metrics=ServiceMetrics(**data["metrics"]),
            )
            for s_id, data in DEFAULT_SERVICES.items()
        }
        self.active_scenario = None
        self.logs_store = {svc: [] for svc in DEFAULT_SERVICES}
        self.metrics_store = {svc: [] for svc in DEFAULT_SERVICES}
        self.events_store = {svc: [] for svc in DEFAULT_SERVICES}

    def load_scenario(self, scenario_id: str) -> Optional[dict]:
        scenario_file = SCENARIOS_DIR / f"{scenario_id}.json"
        if not scenario_file.exists():
            return None
        with open(scenario_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.active_scenario = data

        # Populate telemetry stores from scenario dataset (handoff from Member 4)
        for svc, lines in data.get("logs", {}).items():
            self.logs_store[svc] = [
                LogLine(line=l.get("line", idx + 1), t_s=l.get("t_s", 0.0), text=l.get("text", ""), service=svc)
                for idx, l in enumerate(lines)
            ]

        for ev in data.get("events", []):
            ev_svc = ev.get("service", "postgres")
            if ev_svc in self.events_store:
                self.events_store[ev_svc].append(
                    K8sEvent(t_s=ev.get("t_s", 0.0), service=ev_svc, text=ev.get("text", ""))
                )

        for svc, pts in data.get("metrics", {}).items():
            if svc in self.metrics_store:
                self.metrics_store[svc] = [
                    MetricPoint(t_s=p.get("t_s", 0.0), mem_mb=p.get("mem_mb", 0.0), cpu_pct=p.get("cpu_pct", 0.0), service=svc)
                    for p in pts
                ]

        return data


    async def list_services(self) -> List[ServiceNode]:
        """Returns copies of current ServiceNodes."""
        return [svc.model_copy(deep=True) for svc in self.services.values()]

    async def get_logs(self, service: str, lines: int = 50) -> List[LogLine]:
        """Returns log lines whose t_s <= current playback time, last `lines`."""
        all_logs = self._logs.get(service, [])
        visible = [log for log in all_logs if log.t_s <= self._playback_time]
        return visible[-lines:]

    async def get_metrics(self, service: str) -> List[MetricPoint]:
        return list(self._metrics.get(service, []))

    async def get_events(self, service: str) -> List[K8sEvent]:
        return list(self._events.get(service, []))

    async def apply_action(self, step: PlaybookStep) -> ActionResult:
        """Applies a remediation action. Returns ActionResult."""
        if step.action not in ALLOWED_ACTIONS:
            return ActionResult(
                ok=False,
                message=f"Action '{step.action}' not in ALLOWED_ACTIONS",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

        svc = self.services.get(step.service)
        if not svc:
            return ActionResult(
                ok=False,
                message=f"Unknown service: {step.service}",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

        scenario = self._scenario

        # --- Fix action: clear the fault ---
        if (
            scenario
            and step.action == scenario["fix"]["action"]
            and step.service == scenario["root_service"]
        ):
            self._fault_fixed = True
            # Apply the fix (e.g. patch_memory_limit sets mem_limit_mb)
            if step.action == "patch_memory_limit":
                to_val = step.params.get("to", scenario["fix"]["to"])
                mb = float(to_val.replace("Mi", ""))
                svc.metrics.mem_limit_mb = mb
                # Stabilise memory at ~45 MB
                svc.metrics.mem_mb = 45.0

            svc.status = "recovering"
            await emit("service_update", svc.model_dump(mode="json"))
            await self._sleep(self.step_delay_s)
            svc.status = "healthy"
            await emit("service_update", svc.model_dump(mode="json"))
            self._recompute()
            await self._emit_changed_services()

            return ActionResult(
                ok=True,
                message=f"Fix applied: {step.action} on {step.service}",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

        # --- rollout_restart ---
        if step.action == "rollout_restart":
            svc.status = "recovering"
            svc.metrics.restarts += 1
            await emit("service_update", svc.model_dump(mode="json"))
            await self._sleep(self.step_delay_s)

            # Counts as restarted only if ALL of S's dependencies are healthy
            all_deps_healthy = all(
                self.services[dep].status == "healthy"
                for dep in DEPENDS_ON.get(step.service, [])
            )
            if all_deps_healthy:
                self._restarted_since_fault.add(step.service)
            # else: stays impacted (recompute will set it)

            self._recompute()
            await self._emit_changed_services()

            return ActionResult(
                ok=True,
                message=f"Rollout restart: {step.service}",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

        # --- wait_for_ready / verify_health: no-ops ---
        if step.action in ("wait_for_ready", "verify_health"):
            return ActionResult(
                ok=True,
                message=f"{step.action}: {step.service} (no-op in simulator)",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

        # --- Other allowed actions on unrelated targets ---
        return ActionResult(
            ok=True,
            message=f"{step.action} on {step.service} (no effect in simulator)",
            step_order=step.order,
            service=step.service,
            action=step.action,
        )

    async def probe(self, service: str) -> bool:
        """Returns True only when derived status is healthy."""
        svc = self.services.get(service)
        if not svc:
            return False
        return svc.status == "healthy"

    # ── Extra API (duck-typed, not on Protocol) ──────────────────────────

    async def inject(self, scenario_id: str) -> str:
        """Starts playback of the named scenario. Returns the incident id."""
        # Load from scenarios dir first, fall back to test fixtures
        scenario_path = SCENARIOS_DIR / f"{scenario_id}.json"
        if not scenario_path.exists():
            fixture_path = (
                Path(__file__).resolve().parent.parent / "tests" / "fixtures" / f"{scenario_id}_fixture.json"
            )
            if fixture_path.exists():
                scenario_path = fixture_path
            else:
                raise ValueError(f"Unknown scenario: {scenario_id}")

        if self._scenario is not None:
            raise RuntimeError("A scenario is already running; call reset() first")

        with open(scenario_path, "r", encoding="utf-8") as f:
            self._scenario = json.load(f)

        # Reserve the incident id
        incident_id = f"INC-{self._incident_counter}"
        self._current_incident_id = incident_id
        self._fault_fixed = False
        self._restarted_since_fault.clear()
        self._playback_time = 0.0

        # Pre-load all logs (they become visible as playback_time advances)
        scenario_logs = self._scenario.get("logs", {})
        for svc_id, lines in scenario_logs.items():
            for entry in lines:
                self._logs[svc_id].append(
                    LogLine(line=entry["line"], t_s=entry["t_s"], text=entry["text"], service=svc_id)
                )

        # Start playback task
        task = asyncio.create_task(self._run_playback())
        self._running_tasks.append(task)

        return incident_id

    async def reset(self) -> None:
        """Cancel tasks, restore all services healthy, counter back to 104."""
        # Cancel running tasks
        for task in self._running_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._running_tasks.clear()

        # Restore state
        self.services = _build_default_services()
        self._logs = {s: [] for s in DEPENDS_ON}
        self._metrics = {s: [] for s in DEPENDS_ON}
        self._events = {s: [] for s in DEPENDS_ON}
        self._scenario = None
        self._current_incident_id = None
        self._incident_counter = 104
        self._playback_time = 0.0
        self._fault_fixed = False
        self._restarted_since_fault.clear()

    # ── Playback engine ──────────────────────────────────────────────────

    async def _run_playback(self) -> None:
        """Plays all scenario items in t_s order, ties in file order."""
        scenario = self._scenario
        if not scenario:
            return

        root_service = scenario["root_service"]
        incident_id = self._current_incident_id

        # Build a unified timeline of (t_s, file_order, kind, data)
        timeline: List[tuple] = []
        file_order = 0

        # Metrics
        for svc_id, points in scenario.get("metrics", {}).items():
            for pt in points:
                timeline.append((pt["t_s"], file_order, "metric", svc_id, pt))
                file_order += 1

        # Events
        for ev in scenario.get("events", []):
            timeline.append((ev["t_s"], file_order, "event", ev["service"], ev))
            file_order += 1

        # Alerts
        for alert_data in scenario.get("alerts", []):
            timeline.append((alert_data["t_s"], file_order, "alert", alert_data["service"], alert_data))
            file_order += 1

        # Sort by t_s, then file order (deterministic, ties in file order)
        timeline.sort(key=lambda x: (x[0], x[1]))

        # Playback
        alert_counter = 0
        emitted_alerts: List[Alert] = []
        services_made_root: Set[str] = set()
        services_made_impacted: Set[str] = set()
        prev_t = 0.0

        for t_s, _, kind, svc_id, data in timeline:
            # Advance playback time (sleep for the delta)
            delta = t_s - prev_t
            if delta > 0:
                await self._sleep(delta)
            self._playback_time = t_s
            prev_t = t_s

            if kind == "metric":
                mem = data.get("mem_mb", 0.0)
                cpu = data.get("cpu_pct", 0.0)

                # Emit metric_point
                await emit("metric_point", {
                    "service": svc_id,
                    "t_s": t_s,
                    "mem_mb": mem,
                    "cpu_pct": cpu,
                })

                # Update ServiceNode metrics
                svc = self.services[svc_id]
                svc.metrics.mem_mb = mem
                svc.metrics.cpu_pct = cpu

                # Store metric
                self._metrics[svc_id].append(
                    MetricPoint(t_s=t_s, mem_mb=mem, cpu_pct=cpu, service=svc_id)
                )

                await emit("service_update", svc.model_dump(mode="json"))

            elif kind == "event":
                k8s_event = K8sEvent(t_s=t_s, service=svc_id, text=data["text"])
                self._events[svc_id].append(k8s_event)

                # OOMKilled increments restarts
                if "OOMKilled" in data["text"]:
                    self.services[svc_id].metrics.restarts += 1

                # Root service becomes root_cause at first event or alert
                if svc_id == root_service and svc_id not in services_made_root:
                    self.services[svc_id].status = "root_cause"
                    services_made_root.add(svc_id)
                    await emit("service_update", self.services[svc_id].model_dump(mode="json"))

            elif kind == "alert":
                alert_counter += 1
                now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                alert = Alert(
                    id=f"a-{alert_counter:03d}",
                    ts=now_z,
                    service=svc_id,
                    severity=data["severity"],
                    message=data["message"],
                    incident_id=incident_id,
                )
                emitted_alerts.append(alert)

                await emit("alert", alert.model_dump(mode="json"))

                # Root service becomes root_cause at first event or alert
                if svc_id == root_service and svc_id not in services_made_root:
                    self.services[svc_id].status = "root_cause"
                    services_made_root.add(svc_id)
                    await emit("service_update", self.services[svc_id].model_dump(mode="json"))

                # Other services become impacted at first alert
                if svc_id != root_service and svc_id not in services_made_impacted:
                    self.services[svc_id].status = "impacted"
                    services_made_impacted.add(svc_id)
                    await emit("service_update", self.services[svc_id].model_dump(mode="json"))

        # ── All alerts emitted ────────────────────────────────────────

        # Sanity check: graph.find_root must agree with scenario
        alerting = {a.service for a in emitted_alerts}
        if alerting:
            try:
                computed_root = find_root(alerting)
                if computed_root != root_service:
                    logger.warning(
                        "Sanity check failed: find_root(%s) = %s, expected %s",
                        alerting, computed_root, root_service,
                    )
            except Exception as e:
                logger.warning("Sanity check error: %s", e)

        # Call on_alerts_complete as a separate task (do not block)
        if self.on_alerts_complete is not None:
            asyncio.create_task(self.on_alerts_complete(scenario["id"], emitted_alerts))

        # Wait until duration_s from start
        remaining = scenario["duration_s"] - prev_t
        if remaining > 0:
            await self._sleep(remaining)

    # ── Health recomputation ─────────────────────────────────────────────

    def _recompute(self) -> None:
        """Recompute derived health statuses after an action.

        Rules:
        - Root service: healthy once fixed (_fault_fixed).
        - When root is data-tier, direct dependents need rollout_restart.
        - Other services: healthy automatically once all deps healthy.
        """
        if not self._scenario:
            return

        root = self._scenario["root_service"]
        root_svc = self.services[root]
        root_tier = TIERS.get(root, "")

        # Root: healthy if fixed
        if self._fault_fixed and root_svc.status != "healthy":
            root_svc.status = "healthy"

        # Propagate health
        changed = True
        while changed:
            changed = False
            for svc_id, svc in self.services.items():
                if svc.status == "healthy":
                    continue
                if svc_id == root:
                    continue

                all_deps_healthy = all(
                    self.services[dep].status == "healthy"
                    for dep in DEPENDS_ON.get(svc_id, [])
                )

                if not all_deps_healthy:
                    continue

                # If root is data-tier, direct dependents of root need restart
                is_direct_dep_of_root = root in DEPENDS_ON.get(svc_id, [])
                if root_tier == "data" and is_direct_dep_of_root:
                    if svc_id in self._restarted_since_fault:
                        svc.status = "healthy"
                        changed = True
                    # else: stays impacted/recovering
                else:
                    # Non-direct deps: healthy automatically
                    svc.status = "healthy"
                    changed = True

    async def _emit_changed_services(self) -> None:
        """Emit service_update for all services (after recompute)."""
        for svc in self.services.values():
            await emit("service_update", svc.model_dump(mode="json"))
