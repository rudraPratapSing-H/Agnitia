"""Service topology graph algorithms for Agnitia.

Pure, synchronous, side-effect-free graph operations for correlation,
topological ordering, impacted services computation, and blast radius analysis.
"""

from typing import Dict, List, Set

DEPENDS_ON: Dict[str, List[str]] = {
    "web-ui": ["api-gateway"],
    "api-gateway": ["auth-service", "payment-service"],
    "auth-service": ["postgres", "redis"],
    "payment-service": ["postgres"],
    "postgres": [],
    "redis": [],
}

TIERS: Dict[str, str] = {
    "postgres": "data",
    "redis": "data",
    "auth-service": "backend",
    "payment-service": "backend",
    "api-gateway": "edge",
    "web-ui": "frontend",
}

SERVICE_LABELS: Dict[str, str] = {
    "postgres": "PostgreSQL",
    "redis": "Redis",
    "auth-service": "Auth Service",
    "payment-service": "Payment Service",
    "api-gateway": "API Gateway",
    "web-ui": "Web UI",
}


def topo_order(services: List[str]) -> List[str]:
    """
    Returns topological order of the given services using Kahn's algorithm
    (dependencies first, ties broken alphabetically). Only includes the services passed in.
    """
    for s in services:
        if s not in DEPENDS_ON:
            raise ValueError(f"Unknown service: {s}")

    svc_set = set(services)
    if not svc_set:
        return []

    # In-degree: count of dependencies for node s that are also in svc_set
    in_degree = {
        s: sum(1 for dep in DEPENDS_ON[s] if dep in svc_set)
        for s in svc_set
    }

    # Map each service to dependents that are in svc_set
    dependents_map = {s: [] for s in svc_set}
    for s in svc_set:
        for dep in DEPENDS_ON[s]:
            if dep in svc_set:
                dependents_map[dep].append(s)

    result: List[str] = []
    current_level = sorted([s for s in svc_set if in_degree[s] == 0])

    while current_level:
        next_level = []
        for u in current_level:
            result.append(u)
            for v in dependents_map[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    next_level.append(v)
        current_level = sorted(next_level)

    if len(result) < len(svc_set):
        raise ValueError("Cycle detected in services dependency graph")

    return result


def blast_radius(service: str) -> List[str]:
    """
    Returns every service that transitively depends on `service`, in topological order,
    excluding `service` itself.
    """
    if service not in DEPENDS_ON:
        raise ValueError(f"Unknown service: {service}")

    downstream: Set[str] = set()
    queue = [s for s, deps in DEPENDS_ON.items() if service in deps]

    while queue:
        curr = queue.pop(0)
        if curr not in downstream:
            downstream.add(curr)
            for s, deps in DEPENDS_ON.items():
                if curr in deps and s not in downstream:
                    queue.append(s)

    return topo_order(list(downstream))


def find_root(alerting: Set[str]) -> str:
    """
    Identifies root cause service among alerting services according to the contract:
    an alerting service is the root if none of its direct dependencies are alerting.
    If several qualify, returns the first in topological order.
    Raises ValueError on an empty set or unknown service.
    """
    if not alerting:
        raise ValueError("alerting set cannot be empty")

    for s in alerting:
        if s not in DEPENDS_ON:
            raise ValueError(f"Unknown service: {s}")

    candidates = [
        s for s in alerting
        if not any(dep in alerting for dep in DEPENDS_ON[s])
    ]

    if not candidates:
        return topo_order(list(alerting))[0]

    return topo_order(candidates)[0]


def impacted(root: str, alerting: Set[str]) -> List[str]:
    """
    Returns alerting services transitively downstream of root, excluding root,
    in topological order. Never includes any service that is not in `alerting`.
    """
    if root not in DEPENDS_ON:
        raise ValueError(f"Unknown service: {root}")

    for s in alerting:
        if s not in DEPENDS_ON:
            raise ValueError(f"Unknown service: {s}")

    downstream = set(blast_radius(root))
    affected = downstream.intersection(alerting)
    return topo_order(list(affected))
