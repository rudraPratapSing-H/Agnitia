"""ClusterAdapter Protocol Interface for Agnitia."""

from typing import Protocol, List, Set
from backend.models import (
    ServiceNode,
    LogLine,
    MetricPoint,
    K8sEvent,
    PlaybookStep,
    ActionResult,
)

ALLOWED_ACTIONS: Set[str] = {
    "patch_memory_limit",
    "patch_cpu_limit",
    "rollout_restart",
    "rollback_deployment",
    "scale_replicas",
    "wait_for_ready",
    "verify_health",
}


class ClusterAdapter(Protocol):
    async def list_services(self) -> List[ServiceNode]:
        """Returns the current state of all monitored services."""
        ...

    async def get_logs(self, service: str, lines: int = 50) -> List[LogLine]:
        """Fetches the last N log lines for the given service."""
        ...

    async def get_metrics(self, service: str) -> List[MetricPoint]:
        """Fetches recent metric points for the given service."""
        ...

    async def get_events(self, service: str) -> List[K8sEvent]:
        """Fetches recent cluster/pod events for the given service."""
        ...

    async def apply_action(self, step: PlaybookStep) -> ActionResult:
        """Applies a remediation action (e.g. patch memory limit, restart)."""
        ...

    async def probe(self, service: str) -> bool:
        """Returns True if the service is healthy and responsive."""
        ...
