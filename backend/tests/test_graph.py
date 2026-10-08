"""Unit tests for backend/graph.py verifying correlation, topology, and blast radius"""

import random
import pytest
from backend.graph import (
    DEPENDS_ON,
    TIERS,
    SERVICE_LABELS,
    find_root,
    impacted,
    topo_order,
    blast_radius,
)


def test_fact_1_db_oom_correlation():
    """1. alerting {postgres, auth-service, payment-service, api-gateway, web-ui}:
    root == 'postgres'; impacted == ['auth-service','payment-service','api-gateway','web-ui'] (4 items); 'redis' absent.
    """
    alerting = {"postgres", "auth-service", "payment-service", "api-gateway", "web-ui"}

    root = find_root(alerting)
    assert root == "postgres"

    impacted_services = impacted(root, alerting)
    assert impacted_services == ["auth-service", "payment-service", "api-gateway", "web-ui"]
    assert len(impacted_services) == 4
    assert "redis" not in impacted_services


def test_fact_2_payment_service_crash():
    """2. alerting {payment-service, api-gateway, web-ui}:
    root 'payment-service', impacted ['api-gateway','web-ui'].
    """
    alerting = {"payment-service", "api-gateway", "web-ui"}

    root = find_root(alerting)
    assert root == "payment-service"

    impacted_services = impacted(root, alerting)
    assert impacted_services == ["api-gateway", "web-ui"]


def test_fact_3_blast_radius():
    """3. blast_radius('redis') == ['auth-service','api-gateway','web-ui'] and payment-service is NOT in it;
    blast_radius('postgres') has 4 entries; blast_radius('web-ui') == [].
    """
    redis_radius = blast_radius("redis")
    assert redis_radius == ["auth-service", "api-gateway", "web-ui"]
    assert "payment-service" not in redis_radius

    postgres_radius = blast_radius("postgres")
    assert len(postgres_radius) == 4
    assert postgres_radius == ["auth-service", "payment-service", "api-gateway", "web-ui"]

    web_ui_radius = blast_radius("web-ui")
    assert web_ui_radius == []


def test_fact_4_topo_order_all_6_and_determinism():
    """4. topo_order of all 6: postgres and redis come before auth-service and payment-service,
    then api-gateway, then web-ui; a shuffled input gives the same output.
    """
    all_6 = ["web-ui", "api-gateway", "auth-service", "payment-service", "postgres", "redis"]
    ordered = topo_order(all_6)

    # postgres and redis come before auth-service and payment-service
    idx_pg = ordered.index("postgres")
    idx_redis = ordered.index("redis")
    idx_auth = ordered.index("auth-service")
    idx_pay = ordered.index("payment-service")
    idx_gw = ordered.index("api-gateway")
    idx_ui = ordered.index("web-ui")

    assert idx_pg < idx_auth
    assert idx_pg < idx_pay
    assert idx_redis < idx_auth
    assert idx_redis < idx_pay

    # then api-gateway
    assert idx_auth < idx_gw
    assert idx_pay < idx_gw

    # then web-ui
    assert idx_gw < idx_ui

    # Expected exact alphabetical deterministic ordering
    expected = ["postgres", "redis", "auth-service", "payment-service", "api-gateway", "web-ui"]
    assert ordered == expected

    # Shuffled input must always produce identical output
    for seed in range(10):
        shuffled = list(all_6)
        rng = random.Random(seed)
        rng.shuffle(shuffled)
        assert topo_order(shuffled) == expected


def test_fact_5_error_cases():
    """5. error cases (empty set, unknown service)."""
    # Empty set for find_root raises ValueError
    with pytest.raises(ValueError, match="empty"):
        find_root(set())

    # Unknown service in find_root raises ValueError
    with pytest.raises(ValueError, match="Unknown service"):
        find_root({"unknown-service"})

    with pytest.raises(ValueError, match="Unknown service"):
        find_root({"postgres", "not-a-service"})

    # Unknown service in impacted raises ValueError
    with pytest.raises(ValueError, match="Unknown service"):
        impacted("unknown-root", {"web-ui"})

    with pytest.raises(ValueError, match="Unknown service"):
        impacted("postgres", {"unknown-service"})

    # Unknown service in blast_radius raises ValueError
    with pytest.raises(ValueError, match="Unknown service"):
        blast_radius("unknown-service")

    # Unknown service in topo_order raises ValueError
    with pytest.raises(ValueError, match="Unknown service"):
        topo_order(["unknown-service"])


def test_module_constants():
    """Verify required module constants are defined with exact keys and tiers."""
    assert "postgres" in DEPENDS_ON and "redis" in DEPENDS_ON
    assert TIERS["postgres"] == "data"
    assert TIERS["redis"] == "data"
    assert TIERS["auth-service"] == "backend"
    assert TIERS["payment-service"] == "backend"
    assert TIERS["api-gateway"] == "edge"
    assert TIERS["web-ui"] == "frontend"

    assert SERVICE_LABELS["postgres"] == "PostgreSQL"
    assert SERVICE_LABELS["redis"] == "Redis"
    assert SERVICE_LABELS["auth-service"] == "Auth Service"
    assert SERVICE_LABELS["payment-service"] == "Payment Service"
    assert SERVICE_LABELS["api-gateway"] == "API Gateway"
    assert SERVICE_LABELS["web-ui"] == "Web UI"
