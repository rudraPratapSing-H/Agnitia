"""Deterministic In-Memory Cluster Simulator implementing ClusterAdapter"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from backend.models import (
    ServiceNode,
    ServiceMetrics,
    LogLine,
    MetricPoint,
    K8sEvent,
    PlaybookStep,
    ActionResult,
)
from backend.adapters.base import ClusterAdapter

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"

DEFAULT_SERVICES: Dict[str, dict] = {
    "web-ui": {
        "label": "Web UI",
        "tier": "frontend",
        "depends_on": ["api-gateway"],
        "metrics": {"mem_mb": 42.0, "mem_limit_mb": 128.0, "cpu_pct": 5.0, "restarts": 0},
    },
    "api-gateway": {
        "label": "API Gateway",
        "tier": "edge",
        "depends_on": ["auth-service", "payment-service"],
        "metrics": {"mem_mb": 65.0, "mem_limit_mb": 128.0, "cpu_pct": 14.0, "restarts": 0},
    },
    "auth-service": {
        "label": "Auth Service",
        "tier": "backend",
        "depends_on": ["postgres", "redis"],
        "metrics": {"mem_mb": 50.0, "mem_limit_mb": 128.0, "cpu_pct": 8.0, "restarts": 0},
    },
    "payment-service": {
        "label": "Payment Service",
        "tier": "backend",
        "depends_on": ["postgres"],
        "metrics": {"mem_mb": 72.0, "mem_limit_mb": 128.0, "cpu_pct": 11.0, "restarts": 0},
    },
    "redis": {
        "label": "Redis Cache",
        "tier": "data",
        "depends_on": [],
        "metrics": {"mem_mb": 24.0, "mem_limit_mb": 64.0, "cpu_pct": 3.0, "restarts": 0},
    },
    "postgres": {
        "label": "PostgreSQL",
        "tier": "data",
        "depends_on": [],
        "metrics": {"mem_mb": 58.0, "mem_limit_mb": 64.0, "cpu_pct": 12.0, "restarts": 0},
    },
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
        return list(self.services.values())

    async def get_logs(self, service: str, lines: int = 50) -> List[LogLine]:
        return self.logs_store.get(service, [])[-lines:]

    async def get_metrics(self, service: str) -> List[MetricPoint]:
        return self.metrics_store.get(service, [])

    async def get_events(self, service: str) -> List[K8sEvent]:
        return self.events_store.get(service, [])

    async def apply_action(self, step: PlaybookStep) -> ActionResult:
        svc = self.services.get(step.service)
        if not svc:
            return ActionResult(
                success=False,
                service=step.service,
                action=step.action,
                message=f"Service {step.service} not found",
            )

        # Apply non-destructive allow-listed action
        if step.action == "patch_memory_limit":
            to_val = step.params.get("to", "256Mi")
            mb_val = 256.0 if "256" in to_val else 128.0
            svc.metrics.mem_limit_mb = mb_val
            svc.status = "recovering"
            return ActionResult(
                success=True,
                service=step.service,
                action=step.action,
                message=f"Memory limit patched to {to_val}",
            )

        elif step.action == "rollout_restart":
            svc.metrics.restarts += 1
            svc.status = "recovering"
            return ActionResult(
                success=True,
                service=step.service,
                action=step.action,
                message=f"Deployment for {step.service} restarted successfully",
            )

        elif step.action == "wait_for_ready":
            svc.status = "healthy"
            return ActionResult(
                success=True,
                service=step.service,
                action=step.action,
                message=f"Service {step.service} ready probe succeeded",
            )

        elif step.action == "verify_health":
            svc.status = "healthy"
            return ActionResult(
                success=True,
                service=step.service,
                action=step.action,
                message=f"Health probe check passed for {step.service}",
            )

        return ActionResult(
            success=True,
            service=step.service,
            action=step.action,
            message=f"Action {step.action} executed successfully",
        )

    async def probe(self, service: str) -> bool:
        svc = self.services.get(service)
        if not svc:
            return False
        return svc.status == "healthy" or svc.status == "recovering"
