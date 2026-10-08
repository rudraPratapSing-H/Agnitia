"""Unit tests for graph algorithms and correlation logic"""

from backend.graph import find_root, impacted, topo_order, blast_radius


def test_db_oom_correlation():
    # 56 alerts from db_oom scenario: postgres, auth-service, payment-service, api-gateway, web-ui
    alerting = {"postgres", "auth-service", "payment-service", "api-gateway", "web-ui"}

    # Root cause must be postgres
    root = find_root(alerting)
    assert root == "postgres"

    # Exactly 4 impacted services, and redis must be excluded
    affected = impacted(root, alerting)
    assert len(affected) == 4
    assert "redis" not in affected
    assert set(affected) == {"auth-service", "payment-service", "api-gateway", "web-ui"}


def test_topo_order():
    services = ["web-ui", "api-gateway", "postgres", "auth-service"]
    ordered = topo_order(services)

    # postgres must come before auth-service, auth-service before api-gateway, api-gateway before web-ui
    assert ordered.index("postgres") < ordered.index("auth-service")
    assert ordered.index("auth-service") < ordered.index("api-gateway")
    assert ordered.index("api-gateway") < ordered.index("web-ui")


def test_blast_radius():
    # Blast radius of redis should include auth-service, api-gateway, web-ui
    radius = blast_radius("redis")
    assert "auth-service" in radius
    assert "api-gateway" in radius
    assert "web-ui" in radius
    assert "postgres" not in radius
