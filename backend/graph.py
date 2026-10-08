"""Graph algorithms for service topology and incident correlation"""

from typing import Set, List, Dict

# Service dependencies: service -> list of services it directly depends on
DEPENDENCIES: Dict[str, List[str]] = {
    "web-ui": ["api-gateway"],
    "api-gateway": ["auth-service", "payment-service"],
    "auth-service": ["postgres", "redis"],
    "payment-service": ["postgres"],
    "postgres": [],
    "redis": [],
}

# Reverse dependencies: service -> list of services that depend directly on it
DEPENDENTS: Dict[str, List[str]] = {
    "postgres": ["auth-service", "payment-service"],
    "redis": ["auth-service"],
    "auth-service": ["api-gateway"],
    "payment-service": ["api-gateway"],
    "api-gateway": ["web-ui"],
    "web-ui": [],
}


def find_root(alerting: Set[str]) -> str:
    """
    Finds root cause service among alerting services.
    Rule: An alerting service is the root if none of its dependencies are alerting.
    """
    if not alerting:
        return ""

    candidates = []
    for svc in alerting:
        deps = DEPENDENCIES.get(svc, [])
        # If none of its dependencies are in the alerting set, it's a root candidate
        if not any(dep in alerting for dep in deps):
            candidates.append(svc)

    if not candidates:
        # Fallback to first if cycle or anomalous state
        return next(iter(alerting))

    # If multiple candidates, pick the deepest in dependency tree (e.g. data tier first)
    tier_priority = {"postgres": 0, "redis": 1, "auth-service": 2, "payment-service": 3, "api-gateway": 4, "web-ui": 5}
    candidates.sort(key=lambda s: tier_priority.get(s, 99))
    return candidates[0]


def impacted(root: str, alerting: Set[str]) -> List[str]:
    """
    Returns all alerting services that are downstream of the root cause service.
    Excludes the root service itself.
    """
    if not root:
        return []

    downstream = set(blast_radius(root))
    # Intersect with alerting services and sort topologically
    affected = [svc for svc in alerting if svc in downstream and svc != root]
    return topo_order(affected)


def topo_order(services: List[str]) -> List[str]:
    """
    Orders services such that dependencies come first (safe recovery order).
    """
    svc_set = set(services)
    ordered: List[str] = []
    visited: Set[str] = set()

    def visit(node: str):
        if node in visited:
            return
        visited.add(node)
        for dep in DEPENDENCIES.get(node, []):
            if dep in svc_set:
                visit(dep)
        ordered.append(node)

    for svc in services:
        visit(svc)

    return ordered


def blast_radius(service: str) -> List[str]:
    """
    Returns all services transitively downstream of the given service (all dependents).
    """
    downstream: Set[str] = set()
    queue = list(DEPENDENTS.get(service, []))

    while queue:
        curr = queue.pop(0)
        if curr not in downstream:
            downstream.add(curr)
            queue.extend(DEPENDENTS.get(curr, []))

    return topo_order(list(downstream))
