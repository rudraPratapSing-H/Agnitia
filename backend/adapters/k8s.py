"""Real Kubernetes adapter for Agnitia (Member 2, task 3.2), selected by ADAPTER=k8s.

Hybrid design: only postgres is real (kind cluster, context "kind-agnitia", namespace
"agnitia"); the other five services are driven by an inner SimulatorAdapter. Only the
"db_oom" scenario touches the real cluster -- every other scenario id delegates fully
to the inner simulator, exactly like SimulatorAdapter on its own.

The kubernetes client is synchronous, so every call into it goes through
asyncio.to_thread(). Real behaviour (kind cluster, exec into the pod, kubectl
subprocess) is verified manually; tests mock the kubernetes client.
"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from kubernetes import client, config
from kubernetes.stream import stream as k8s_stream

from backend.adapters.base import ALLOWED_ACTIONS
from backend.adapters.simulator import SimulatorAdapter
from backend.bus import emit
from backend.graph import DEPENDS_ON, SERVICE_LABELS, TIERS
from backend.models import (
    ActionResult,
    K8sEvent,
    LogLine,
    MetricPoint,
    PlaybookStep,
    ServiceMetrics,
    ServiceNode,
)

logger = logging.getLogger(__name__)

K8S_DIR = Path(__file__).resolve().parent.parent.parent / "k8s"
MEMORY_HOG_YAML = K8S_DIR / "memory-hog.yaml"

POD_NAME = "postgres-0"
STATEFULSET_NAME = "postgres"
CONTAINER_NAME = "postgres"
BASELINE_MEM_LIMIT = "64Mi"  # matches k8s/postgres.yaml and k8s/reset.sh

POLL_INTERVAL_S = 0.5  # metrics/termination poll cadence, per task 3.2


def _mi_to_mb(value: str) -> float:
    """'256Mi' -> 256.0. Falls back to 0.0 for an unparsable value."""
    try:
        return float(str(value).rstrip("Mi").rstrip("i").rstrip("M"))
    except (TypeError, ValueError):
        return 0.0


def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class K8sAdapter:
    """Connects to a real kind cluster for postgres; delegates everything else."""

    def __init__(self, context: str = "kind-agnitia", namespace: str = "agnitia") -> None:
        self.context = context
        self.namespace = namespace

        self._core_v1: Optional[client.CoreV1Api] = None
        self._apps_v1: Optional[client.AppsV1Api] = None

        self._inner = SimulatorAdapter()
        self.on_alerts_complete = None  # set by main.py; propagated to self._inner when used

        # Duck-typed extras main.py reads directly (mirrors SimulatorAdapter).
        self._scenario: Optional[dict] = None
        self._running_tasks: List[asyncio.Task] = []
        self._incident_counter = 104

        self._t0_wall: Optional[datetime] = None
        self._postgres = ServiceNode(
            id="postgres",
            label=SERVICE_LABELS["postgres"],
            tier=TIERS["postgres"],
            depends_on=list(DEPENDS_ON["postgres"]),
            status="healthy",
            metrics=ServiceMetrics(mem_mb=40.0, mem_limit_mb=_mi_to_mb(BASELINE_MEM_LIMIT), cpu_pct=12.0, restarts=0),
        )
        self._postgres_metrics: List[MetricPoint] = []
        self._postgres_events: List[K8sEvent] = []
        self._db_oom_triggered = False  # this run's real OOM already fired the alert cascade

    # ── kubernetes client (lazy; wraps the sync client in a thread) ─────────

    async def _ensure_clients(self) -> None:
        if self._core_v1 is not None:
            return

        def _load() -> tuple:
            config.load_kube_config(context=self.context)
            return client.CoreV1Api(), client.AppsV1Api()

        self._core_v1, self._apps_v1 = await asyncio.to_thread(_load)

    def _elapsed(self, ts: Optional[datetime]) -> float:
        if ts is None or self._t0_wall is None:
            return 0.0
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, round((ts - self._t0_wall).total_seconds(), 2))

    # ── ClusterAdapter Protocol methods ──────────────────────────────────

    async def list_services(self) -> List[ServiceNode]:
        services = await self._inner.list_services()
        return [self._postgres.model_copy(deep=True) if s.id == "postgres" else s for s in services]

    async def get_logs(self, service: str, lines: int = 50) -> List[LogLine]:
        if service != "postgres":
            return await self._inner.get_logs(service, lines)

        await self._ensure_clients()
        try:
            pod = await asyncio.to_thread(self._core_v1.read_namespaced_pod, POD_NAME, self.namespace)
            statuses = pod.status.container_statuses or []
            restarted = bool(statuses and statuses[0].restart_count > 0)
            raw = await asyncio.to_thread(
                self._core_v1.read_namespaced_pod_log,
                POD_NAME,
                self.namespace,
                previous=restarted,
                timestamps=True,
                tail_lines=lines,
            )
        except Exception as exc:
            logger.warning("k8s: get_logs(postgres) failed: %s", exc)
            return []

        out: List[LogLine] = []
        for idx, raw_line in enumerate((raw or "").splitlines(), start=1):
            ts_str, _, text = raw_line.partition(" ")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                ts, text = None, raw_line
            out.append(LogLine(line=idx, t_s=self._elapsed(ts), text=text, service="postgres"))
        return out[-lines:]

    async def get_metrics(self, service: str) -> List[MetricPoint]:
        if service != "postgres":
            return await self._inner.get_metrics(service)
        return list(self._postgres_metrics)

    async def get_events(self, service: str) -> List[K8sEvent]:
        if service != "postgres":
            return await self._inner.get_events(service)

        events = list(self._postgres_events)
        await self._ensure_clients()
        try:
            api_events = await asyncio.to_thread(
                self._core_v1.list_namespaced_event,
                self.namespace,
                field_selector=f"involvedObject.name={POD_NAME}",
            )
            for ev in getattr(api_events, "items", None) or []:
                ts = ev.last_timestamp or ev.event_time or ev.first_timestamp
                events.append(K8sEvent(t_s=self._elapsed(ts), service="postgres", text=f"{ev.reason}: {ev.message}"))
        except Exception as exc:
            logger.warning("k8s: get_events(postgres) live fetch failed: %s", exc)
        return events

    async def apply_action(self, step: PlaybookStep) -> ActionResult:
        if step.service != "postgres":
            return await self._inner.apply_action(step)

        if step.action not in ALLOWED_ACTIONS:
            return ActionResult(
                ok=False,
                message=f"Action '{step.action}' not in ALLOWED_ACTIONS",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

        await self._ensure_clients()
        try:
            if step.action in ("patch_memory_limit", "patch_cpu_limit"):
                return await self._patch_resource_limit(step)
            if step.action == "rollout_restart":
                return await self._rollout_restart_postgres(step)
            if step.action in ("wait_for_ready", "verify_health"):
                # Real verification happens via probe(), which executor.py already
                # polls after every step; apply_action only needs to kick the step off.
                return ActionResult(
                    ok=True,
                    message=f"{step.action}: postgres (verified via probe)",
                    step_order=step.order,
                    service=step.service,
                    action=step.action,
                )
            # scale_replicas / rollback_deployment: the PRD defines no real translation
            # for a bare postgres StatefulSet, and db_oom's playbook never issues these
            # against postgres. Simplest option consistent with the PRD: delegate to the
            # inner simulator's generic no-op handling rather than inventing one.
            return await self._inner.apply_action(step)
        except Exception as exc:
            return ActionResult(
                ok=False,
                message=f"k8s error: {exc}",
                step_order=step.order,
                service=step.service,
                action=step.action,
            )

    async def _patch_resource_limit(self, step: PlaybookStep) -> ActionResult:
        resource_key = "memory" if step.action == "patch_memory_limit" else "cpu"
        to_val = (step.params or {}).get("to")
        if not to_val:
            return ActionResult(
                ok=False, message="missing params.to", step_order=step.order,
                service=step.service, action=step.action,
            )
        body = {
            "spec": {"template": {"spec": {"containers": [
                {"name": CONTAINER_NAME, "resources": {"limits": {resource_key: to_val}}}
            ]}}}
        }
        await asyncio.to_thread(
            self._apps_v1.patch_namespaced_stateful_set, STATEFULSET_NAME, self.namespace, body
        )
        if resource_key == "memory":
            self._postgres.metrics.mem_limit_mb = _mi_to_mb(to_val)
        return ActionResult(
            ok=True, message=f"patched postgres {resource_key} limit to {to_val}",
            step_order=step.order, service=step.service, action=step.action,
        )

    async def _rollout_restart_postgres(self, step: PlaybookStep) -> ActionResult:
        body = {"spec": {"template": {"metadata": {"annotations": {
            "kubectl.kubernetes.io/restartedAt": _now_z()
        }}}}}
        await asyncio.to_thread(
            self._apps_v1.patch_namespaced_stateful_set, STATEFULSET_NAME, self.namespace, body
        )
        return ActionResult(
            ok=True, message="rollout restart triggered via restartedAt annotation",
            step_order=step.order, service=step.service, action=step.action,
        )

    async def probe(self, service: str) -> bool:
        if service != "postgres":
            return await self._inner.probe(service)

        await self._ensure_clients()
        try:
            pod = await asyncio.to_thread(self._core_v1.read_namespaced_pod, POD_NAME, self.namespace)
        except Exception:
            return False

        ready = any(
            c.type == "Ready" and c.status == "True" for c in (pod.status.conditions or [])
        )
        if ready:
            self._postgres.status = "healthy"
        return ready

    # ── Extra API (duck-typed, matching SimulatorAdapter) ────────────────

    async def inject(self, scenario_id: str) -> str:
        if self._scenario is not None:
            raise RuntimeError("A scenario is already running; call reset() first")

        scenario_path = Path(__file__).resolve().parent.parent / "scenarios" / f"{scenario_id}.json"
        if not scenario_path.exists():
            raise ValueError(f"Unknown scenario: {scenario_id}")
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        self._scenario = scenario

        if scenario_id != "db_oom":
            # Every other scenario id delegates fully to the inner simulator.
            incident_id = await self._inner.inject(scenario_id)
            self._running_tasks = list(self._inner._running_tasks)
            return incident_id

        incident_id = f"INC-{self._incident_counter}"
        self._t0_wall = datetime.now(timezone.utc)
        self._db_oom_triggered = False
        self._postgres_metrics = []
        self._postgres_events = []

        task = asyncio.create_task(self._run_real_db_oom(scenario))
        self._running_tasks = [task]
        return incident_id

    async def reset(self) -> None:
        for task in self._running_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._running_tasks.clear()

        if self._scenario is not None and self._scenario.get("id") == "db_oom":
            await self._real_reset_postgres()

        await self._inner.reset()
        self._scenario = None
        self._t0_wall = None
        self._db_oom_triggered = False
        self._postgres_metrics = []
        self._postgres_events = []
        self._postgres = ServiceNode(
            id="postgres",
            label=SERVICE_LABELS["postgres"],
            tier=TIERS["postgres"],
            depends_on=list(DEPENDS_ON["postgres"]),
            status="healthy",
            metrics=ServiceMetrics(mem_mb=40.0, mem_limit_mb=_mi_to_mb(BASELINE_MEM_LIMIT), cpu_pct=12.0, restarts=0),
        )

    async def _real_reset_postgres(self) -> None:
        await self._ensure_clients()
        try:
            await asyncio.to_thread(self._run_kubectl, ["delete", "job", "memory-hog", "-n", self.namespace, "--ignore-not-found=true"])
            body = {"spec": {"template": {"spec": {"containers": [
                {"name": CONTAINER_NAME, "resources": {"limits": {"memory": BASELINE_MEM_LIMIT}}}
            ]}}}}
            await asyncio.to_thread(
                self._apps_v1.patch_namespaced_stateful_set, STATEFULSET_NAME, self.namespace, body
            )
            deadline = asyncio.get_running_loop().time() + 60.0
            while asyncio.get_running_loop().time() < deadline:
                if await self.probe("postgres"):
                    break
                await asyncio.sleep(POLL_INTERVAL_S)
        except Exception as exc:
            logger.warning("k8s: real reset of postgres failed: %s", exc)

    # ── The real db_oom run ───────────────────────────────────────────────

    async def _run_real_db_oom(self, scenario: dict) -> None:
        await self._ensure_clients()
        try:
            await asyncio.to_thread(self._run_kubectl, ["apply", "-f", str(MEMORY_HOG_YAML)])
        except Exception as exc:
            logger.warning("k8s: kubectl apply memory-hog failed: %s", exc)

        while True:
            await self._poll_postgres_once(scenario)
            if self._db_oom_triggered:
                return
            await asyncio.sleep(POLL_INTERVAL_S)

    @staticmethod
    def _run_kubectl(args: List[str]) -> None:
        subprocess.run(["kubectl", *args], check=False, capture_output=True, text=True)

    async def _poll_postgres_once(self, scenario: dict) -> None:
        mem_mb = await self._read_postgres_mem_mb()
        t_s = self._elapsed(datetime.now(timezone.utc))

        self._postgres.metrics.mem_mb = mem_mb
        point = MetricPoint(t_s=t_s, mem_mb=mem_mb, cpu_pct=0.0, service="postgres")
        self._postgres_metrics.append(point)
        await emit("metric_point", point.model_dump(mode="json"))
        await emit("service_update", self._postgres.model_dump(mode="json"))

        try:
            pod = await asyncio.to_thread(self._core_v1.read_namespaced_pod, POD_NAME, self.namespace)
        except Exception as exc:
            logger.warning("k8s: read_namespaced_pod(postgres) failed: %s", exc)
            return

        statuses = pod.status.container_statuses or []
        terminated = statuses[0].last_state.terminated if statuses else None
        if terminated and terminated.reason == "OOMKilled":
            await self._on_real_oom(scenario, terminated)

    async def _read_postgres_mem_mb(self) -> float:
        exec_command = ["cat", "/sys/fs/cgroup/memory.current"]
        try:
            raw = await asyncio.to_thread(
                k8s_stream,
                self._core_v1.connect_get_namespaced_pod_exec,
                POD_NAME, self.namespace,
                command=exec_command, stderr=True, stdin=False, stdout=True, tty=False,
            )
            return round(int(raw.strip()) / (1024 * 1024), 2)
        except Exception:
            pass

        exec_command_v1 = ["cat", "/sys/fs/cgroup/memory/memory.usage_in_bytes"]
        try:
            raw = await asyncio.to_thread(
                k8s_stream,
                self._core_v1.connect_get_namespaced_pod_exec,
                POD_NAME, self.namespace,
                command=exec_command_v1, stderr=True, stdin=False, stdout=True, tty=False,
            )
            return round(int(raw.strip()) / (1024 * 1024), 2)
        except Exception as exc:
            logger.warning("k8s: could not read postgres memory (cgroup v2 or v1): %s", exc)
            return self._postgres.metrics.mem_mb

    async def _on_real_oom(self, scenario: dict, terminated: Any) -> None:
        self._db_oom_triggered = True

        exit_code = terminated.exit_code
        text = f"Reason: OOMKilled, Exit Code: {exit_code}"
        self._postgres_events.append(
            K8sEvent(t_s=self._elapsed(datetime.now(timezone.utc)), service="postgres", text=text)
        )

        self._postgres.status = "root_cause"
        self._postgres.metrics.restarts += 1
        await emit("service_update", self._postgres.model_dump(mode="json"))

        await self._play_alert_cascade(scenario)

    async def _play_alert_cascade(self, scenario: dict) -> None:
        """Plays the scenario's 56-alert cascade via the inner simulator, same ids and
        reserved incident id as a normal simulated run. Postgres' own metrics/events are
        real (handled above), so the inner simulator is primed with just the alerts.
        """
        alerts_raw = scenario.get("alerts", [])
        if not alerts_raw:
            if self.on_alerts_complete is not None:
                await self.on_alerts_complete(scenario["id"], [])
            return

        await self._inner.reset()
        base_t = min(a["t_s"] for a in alerts_raw)
        trimmed_alerts = [{**a, "t_s": round(a["t_s"] - base_t, 3)} for a in alerts_raw]

        inner = self._inner
        inner.on_alerts_complete = self.on_alerts_complete
        inner._scenario = {
            **scenario,
            "metrics": {},
            "events": [],
            "alerts": trimmed_alerts,
            "duration_s": max(a["t_s"] for a in trimmed_alerts),
        }
        inner._current_incident_id = f"INC-{inner._incident_counter}"
        inner._playback_time = 0.0
        inner.services[scenario["root_service"]].status = "root_cause"

        task = asyncio.create_task(inner._run_playback())
        self._running_tasks.append(task)
        await task
