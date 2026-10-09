"""Service topology graph algorithms for Agnitia.

Supports both Standard K8s Core (6 services) and Amazon Hyperscale (20 services).
Pure, synchronous, side-effect-free graph operations for correlation,
topological ordering, impacted services computation, and blast radius analysis.
"""

from typing import Dict, List, Set, Iterable

# ── Preset 1: Standard K8s Core (Mirrors CONTRACT.md Exactly) ────────────────
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

# ── Preset 2: Amazon Hyperscale Topology (20 Services) ────────────────────────
AMAZON_DEPENDS_ON: Dict[str, List[str]] = {
    "cloud-front": ["web-storefront", "mobile-bff"],
    "web-storefront": ["api-gateway", "search-service", "recommendation-engine"],
    "mobile-bff": ["api-gateway", "search-service"],
    "shipping-service": ["sqs-event-bus"],
    "notification-service": ["sqs-event-bus"],
    "sqs-event-bus": ["order-service"],
    "order-service": ["aurora-orders-db", "payment-service", "inventory-service"],
    "cart-service": ["dynamodb-cart", "product-catalog"],
    "product-catalog": ["redis-cache"],
    "search-service": ["opensearch-cluster"],
    "inventory-service": ["warehouse-db"],
    "recommendation-engine": ["redis-cache"],
    "auth-service": ["redis-cache"],
    "payment-service": ["aurora-orders-db"],
    "api-gateway": ["auth-service", "order-service", "cart-service", "product-catalog"],
    "aurora-orders-db": [],
    "dynamodb-cart": [],
    "redis-cache": [],
    "opensearch-cluster": [],
    "warehouse-db": [],
}

AMAZON_TIERS: Dict[str, str] = {
    "aurora-orders-db": "data",
    "dynamodb-cart": "data",
    "redis-cache": "data",
    "opensearch-cluster": "data",
    "warehouse-db": "data",
    "payment-service": "backend",
    "inventory-service": "backend",
    "order-service": "backend",
    "cart-service": "backend",
    "product-catalog": "backend",
    "search-service": "backend",
    "auth-service": "backend",
    "recommendation-engine": "backend",
    "sqs-event-bus": "backend",
    "notification-service": "backend",
    "shipping-service": "backend",
    "api-gateway": "edge",
    "web-storefront": "frontend",
    "mobile-bff": "frontend",
    "cloud-front": "edge",
}

AMAZON_SERVICE_LABELS: Dict[str, str] = {
    "aurora-orders-db": "Aurora PostgreSQL",
    "dynamodb-cart": "DynamoDB Cart",
    "redis-cache": "ElastiCache Redis",
    "opensearch-cluster": "OpenSearch Cluster",
    "warehouse-db": "Warehouse MySQL",
    "payment-service": "Amazon Pay Gateway",
    "inventory-service": "Inventory Allocation",
    "order-service": "Order Orchestrator",
    "cart-service": "Cart & Checkout",
    "product-catalog": "Product Catalog",
    "search-service": "Search & Discovery",
    "auth-service": "Cognito / IAM Auth",
    "recommendation-engine": "Personalization AI",
    "sqs-event-bus": "SQS Event Bus",
    "notification-service": "SNS / SES Notifier",
    "shipping-service": "Logistics & Shipping",
    "api-gateway": "Amazon API Gateway",
    "web-storefront": "Storefront Web UI",
    "mobile-bff": "Mobile App BFF",
    "cloud-front": "CloudFront CDN & WAF",
}


def _resolve_graph(services: Iterable[str]) -> Dict[str, List[str]]:
    """Chooses between K8s Core graph and Amazon Hyperscale graph based on services present."""
    svc_list = list(services)
    if any(s in AMAZON_DEPENDS_ON and s not in DEPENDS_ON for s in svc_list):
        return AMAZON_DEPENDS_ON
    return DEPENDS_ON


def topo_order(services: List[str]) -> List[str]:
    """
    Returns topological order of the given services using Kahn's algorithm
    (dependencies first, ties broken alphabetically). Only includes the services passed in.
    """
    graph = _resolve_graph(services)

    for s in services:
        if s not in graph:
            raise ValueError(f"Unknown service: {s}")

    svc_set = set(services)
    if not svc_set:
        return []

    # In-degree: count of dependencies for node s that are also in svc_set
    in_degree = {
        s: sum(1 for dep in graph[s] if dep in svc_set)
        for s in svc_set
    }

    # Map each service to dependents that are in svc_set
    dependents_map = {s: [] for s in svc_set}
    for s in svc_set:
        for dep in graph[s]:
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


def blast_radius(service: str, preset: str = "auto") -> List[str]:
    """
    Returns every service that transitively depends on `service`, in topological order,
    excluding `service` itself.
    """
    if preset == "amazon" or (preset == "auto" and service in AMAZON_DEPENDS_ON and service not in DEPENDS_ON):
        graph = AMAZON_DEPENDS_ON
    else:
        graph = DEPENDS_ON

    if service not in graph:
        raise ValueError(f"Unknown service: {service}")

    downstream: Set[str] = set()
    queue = [s for s, deps in graph.items() if service in deps]

    while queue:
        curr = queue.pop(0)
        if curr not in downstream:
            downstream.add(curr)
            for s, deps in graph.items():
                if curr in deps and s not in downstream:
                    queue.append(s)

    # Use graph for topo_order of downstream
    svc_set = set(downstream)
    if not svc_set:
        return []

    in_degree = {s: sum(1 for dep in graph[s] if dep in svc_set) for s in svc_set}
    dependents_map = {s: [] for s in svc_set}
    for s in svc_set:
        for dep in graph[s]:
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

    return result


def find_root(alerting: Set[str]) -> str:
    """
    Identifies root cause service among alerting services according to the contract:
    an alerting service is the root if none of its direct dependencies are alerting.
    If several qualify, returns the first in topological order.
    Raises ValueError on an empty set or unknown service.
    """
    if not alerting:
        raise ValueError("alerting set cannot be empty")

    graph = _resolve_graph(alerting)

    for s in alerting:
        if s not in graph:
            raise ValueError(f"Unknown service: {s}")

    candidates = [
        s for s in alerting
        if not any(dep in alerting for dep in graph[s])
    ]

    if not candidates:
        return topo_order(list(alerting))[0]

    return topo_order(candidates)[0]


def impacted(root: str, alerting: Set[str]) -> List[str]:
    """
    Returns alerting services transitively downstream of root, excluding root,
    in topological order. Never includes any service that is not in `alerting`.
    """
    graph = _resolve_graph(set(list(alerting) + [root]))

    if root not in graph:
        raise ValueError(f"Unknown service: {root}")

    for s in alerting:
        if s not in graph:
            raise ValueError(f"Unknown service: {s}")

    preset_name = "amazon" if graph is AMAZON_DEPENDS_ON else "k8s"
    downstream = set(blast_radius(root, preset=preset_name))
    affected = downstream.intersection(alerting)
    return topo_order(list(affected))
