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


def _parse_mb(val: Any) -> float:
    """Parses memory limit values like '64Mi', '256MB', '128', 128, 64.0 into float MB."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        v = val.strip()
        for suffix in ("Mi", "MB", "M", "Gi", "GB", "G"):
            if v.endswith(suffix):
                num = float(v[:-len(suffix)])
                if suffix.startswith("G"):
                    return num * 1024.0
                return num
        return float(v)
    raise ValueError(f"Cannot parse memory limit: {val!r}")


def _build_default_services() -> Dict[str, ServiceNode]:
    """Builds fresh healthy ServiceNodes from graph constants."""
    services: Dict[str, ServiceNode] = {}
    for svc_id in DEPENDS_ON:
        defaults = _DEFAULT_METRICS.get(svc_id, {"mem_mb": 50.0, "cpu_pct": 10.0})
        limit = _DEFAULT_MEM_LIMITS.get(svc_id, 128.0)
        services[svc_id] = ServiceNode(
            id=svc_id,
            label=SERVICE_LABELS[svc_id],
            tier=TIERS[svc_id],
            depends_on=list(DEPENDS_ON[svc_id]),
            status="healthy",
            metrics=ServiceMetrics(
                mem_mb=defaults["mem_mb"],
                mem_limit_mb=limit,
                cpu_pct=defaults["cpu_pct"],
                restarts=0,
            ),
        )
    return services


class SimulatorAdapter:
    """Deterministic cluster simulator that plays scenario files on a timeline."""

    def __init__(
        self,
        speed: Optional[float] = None,
        step_delay_s: Optional[float] = None,
    ) -> None:
        self.speed: float = speed if speed is not None else float(os.getenv("SIM_SPEED", "1.0"))
        self.step_delay_s: float = (
            step_delay_s if step_delay_s is not None else float(os.getenv("SIM_STEP_DELAY_S", "2.0"))
        )

        # State
        self.services: Dict[str, ServiceNode] = _build_default_services()
        self._logs: Dict[str, List[LogLine]] = {s: [] for s in DEPENDS_ON}
        self._metrics: Dict[str, List[MetricPoint]] = {s: [] for s in DEPENDS_ON}
        self._events: Dict[str, List[K8sEvent]] = {s: [] for s in DEPENDS_ON}
        self._cpu_limits: Dict[str, dict] = {}
        self._replica_scales: Dict[str, dict] = {}

        self._scenario: Optional[Dict[str, Any]] = None
        self._incident_counter: int = 104
        self._current_incident_id: Optional[str] = None
        self._playback_time: float = 0.0
        self._fault_fixed: bool = False
        self._restarted_since_fault: Set[str] = set()
        self._running_tasks: List[asyncio.Task] = []

        # Callback set by main.py
        self.on_alerts_complete: Optional[Callable] = None

    async def _sleep(self, seconds: float) -> None:
        """All waiting goes through here so tests can run at speed=200."""
        if seconds <= 0:
            return
        await asyncio.sleep(seconds / self.speed)

    # ── ClusterAdapter Protocol methods ──────────────────────────────────

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

        # --- patch_memory_limit: accepts both {"from":"64Mi","to":"256Mi"} and {"from_mb":64,"to_mb":128} ---
        if step.action == "patch_memory_limit":
            to_val = None
            if step.params:
                if "to_mb" in step.params:
                    to_val = step.params["to_mb"]
                elif "to" in step.params:
                    to_val = step.params["to"]
            if to_val is None and scenario and "fix" in scenario and "to" in scenario["fix"]:
                to_val = scenario["fix"]["to"]
            target_mb = _parse_mb(to_val) if to_val is not None else svc.metrics.mem_limit_mb
            svc.metrics.mem_limit_mb = target_mb

            # If it matches the scenario's fix action on the root service
            if (
                scenario
                and step.service == scenario.get("root_service")
                and scenario.get("fix", {}).get("action") == "patch_memory_limit"
            ):
                self._fault_fixed = True
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
            else:
                await emit("service_update", svc.model_dump(mode="json"))
                return ActionResult(
                    ok=True,
                    message=f"Patched memory limit on {step.service} to {target_mb}MB",
                    step_order=step.order,
                    service=step.service,
                    action=step.action,
                )

        # --- General fix action: clear the fault for non-memory fixes ---
        if (
            scenario
            and step.action == scenario.get("fix", {}).get("action")
            and step.service == scenario.get("root_service")
        ):
            self._fault_fixed = True
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

        # --- patch_cpu_limit: accepted and stored with no visible effect ---
        if step.action == "patch_cpu_limit":
            self._cpu_limits[step.service] = step.params or {}
            return ActionResult(
                ok=True,
                message=f"patch_cpu_limit on {step.service} accepted (stored)",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

        # --- scale_replicas: accepted and stored with no visible effect ---
        if step.action == "scale_replicas":
            self._replica_scales[step.service] = step.params or {}
            return ActionResult(
                ok=True,
                message=f"scale_replicas on {step.service} accepted (stored)",
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
        if os.getenv("SIM_FORCE_PROBE_FAIL") == "1":
            return False
        svc = self.services.get(service)
        if not svc:
            return False
        return svc.status == "healthy"

    # ── Extra API (duck-typed, not on Protocol) ──────────────────────────

    async def inject(self, scenario_id: str) -> str:
        """Starts playback of the named scenario. Returns the incident id."""
        if self._scenario is not None:
            raise RuntimeError("A scenario is already running; call reset() first")

        # Load from scenarios dir first, fall back to test fixtures or synth generator
        scenario_path = SCENARIOS_DIR / f"{scenario_id}.json"
        if scenario_path.exists():
            with open(scenario_path, "r", encoding="utf-8") as f:
                self._scenario = json.load(f)
        elif scenario_id in ("healthy_spike", "sawtooth"):
            import numpy as np
            from backend.ml.synth import generate_run
            from backend.ml.config import DEMO_SEED
            kind = "spike" if scenario_id == "healthy_spike" else "sawtooth"
            points, _ = generate_run(kind, np.random.default_rng(DEMO_SEED))
            self._scenario = {
                "id": scenario_id,
                "title": f"Synthetic {scenario_id}",
                "root_service": "postgres",
                "duration_s": 300,
                "metrics": {"postgres": points},
                "events": [],
                "logs": {},
                "alerts": [],
                "fix": {},
            }
        else:
            fixture_path = (
                Path(__file__).resolve().parent.parent / "tests" / "fixtures" / f"{scenario_id}_fixture.json"
            )
            if fixture_path.exists():
                with open(fixture_path, "r", encoding="utf-8") as f:
                    self._scenario = json.load(f)
            else:
                raise ValueError(f"Unknown scenario: {scenario_id}")

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
        self._cpu_limits.clear()
        self._replica_scales.clear()
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
                svc = self.services[svc_id]
                mem = float(data.get("mem_mb", 0.0))
                cpu = float(data.get("cpu_pct", 0.0))
                mem_limit_mb = float(data.get("mem_limit_mb", svc.metrics.mem_limit_mb))
                restarts = int(data.get("restarts", svc.metrics.restarts))
                err_pct = float(data.get("err_pct", 0.0))

                # Emit metric_point (7 keys)
                await emit("metric_point", {
                    "service": svc_id,
                    "t_s": t_s,
                    "mem_mb": mem,
                    "mem_limit_mb": mem_limit_mb,
                    "cpu_pct": cpu,
                    "restarts": restarts,
                    "err_pct": err_pct,
                })

                # Update ServiceNode metrics
                svc.metrics.mem_mb = mem
                svc.metrics.cpu_pct = cpu

                # Store metric
                self._metrics[svc_id].append(
                    MetricPoint(
                        t_s=t_s,
                        mem_mb=mem,
                        cpu_pct=cpu,
                        service=svc_id,
                        mem_limit_mb=mem_limit_mb,
                        restarts=restarts,
                        err_pct=err_pct,
                    )
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
