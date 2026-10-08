"""
Tests for Phase 0 Deliverables — Member 4 (Integrations & Content)
- Task 0.5: scenarios/db_oom.json validation and alert count (56 alerts)
- Task 0.6: Telegram bot ping/pong handling, card generation, and approval flow
"""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
import pytest

from bot.telegram_bot import AgnitiaBotEngine, bot_engine
from backend.models import (
    ServiceNode,
    Alert,
    EvidenceItem,
    RCA,
    PlaybookStep,
    Playbook,
    Incident,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = REPO_ROOT / "backend" / "scenarios"
DB_OOM_PATH = SCENARIOS_DIR / "db_oom.json"


@pytest.fixture
def db_oom_data():
    assert DB_OOM_PATH.exists(), f"Scenario file does not exist at {DB_OOM_PATH}"
    with open(DB_OOM_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================================================
# Task 0.5 Tests: Scenario db_oom.json & Count Script
# =====================================================================

def test_db_oom_schema_completeness(db_oom_data):
    """Validates that db_oom.json satisfies the CONTRACT.md scenario format."""
    required_keys = ["id", "title", "root_service", "duration_s", "metrics", "events", "logs", "alerts", "fix"]
    for k in required_keys:
        assert k in db_oom_data, f"Missing required top-level key: {k}"

    assert db_oom_data["id"] == "db_oom"
    assert db_oom_data["root_service"] == "postgres"
    assert db_oom_data["duration_s"] == 12


def test_db_oom_metrics_curve(db_oom_data):
    """Verifies that postgres memory curve ramps from 40Mi to 64Mi over 6 seconds."""
    pg_metrics = db_oom_data["metrics"].get("postgres", [])
    assert len(pg_metrics) >= 10, "Should have at least 10 telemetry points"

    first_pt = pg_metrics[0]
    peak_pt = pg_metrics[-1]

    assert first_pt["mem_mb"] == 40.0
    assert peak_pt["mem_mb"] == 64.0
    assert peak_pt["t_s"] == 6.0


def test_db_oom_events_and_fatal_citation(db_oom_data):
    """Verifies OOMKilled 137 event and log line 42 citation match."""
    # K8s events
    events = db_oom_data.get("events", [])
    assert any("OOMKilled" in e["text"] and "137" in e["text"] for e in events)

    # Postgres logs
    pg_logs = db_oom_data["logs"].get("postgres", [])
    assert len(pg_logs) >= 50

    line_42 = next((l for l in pg_logs if l["line"] == 42), None)
    assert line_42 is not None
    assert "FATAL: out of memory" in line_42["text"]


def test_db_oom_exact_56_alerts_and_graph_breakdown(db_oom_data):
    """
    Verifies CONTRACT.md Section 1 correlation rule:
    - Exactly 56 raw alerts
    - postgres (root cause): 1
    - auth-service (impacted): 10
    - payment-service (impacted): 15
    - api-gateway (impacted): 18
    - web-ui (impacted): 12
    - redis (healthy): 0
    """
    alerts = db_oom_data.get("alerts", [])
    assert len(alerts) == 56, f"Expected exactly 56 alerts, got {len(alerts)}"

    counts = Counter(a["service"] for a in alerts)
    assert counts["postgres"] == 1
    assert counts["auth-service"] == 10
    assert counts["payment-service"] == 15
    assert counts["api-gateway"] == 18
    assert counts["web-ui"] == 12
    assert counts.get("redis", 0) == 0


def test_db_oom_remediation_fix(db_oom_data):
    """Verifies non-destructive memory patch fix."""
    fix = db_oom_data.get("fix", {})
    assert fix.get("action") == "patch_memory_limit"
    assert fix.get("from") == "64Mi"
    assert fix.get("to") == "256Mi"


def test_count_script_prints_56():
    """
    Task 0.5 Acceptance Criteria:
    'a count script prints 56'
    """
    script_path = REPO_ROOT / "scripts" / "count_alerts.py"
    assert script_path.exists(), "scripts/count_alerts.py must exist"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout.strip()
    assert output == "56", f"Count script must print '56', got '{output}'"


# =====================================================================
# Task 0.6 Tests: Telegram Bot (Ping/Pong, Card, and Approval Logic)
# =====================================================================

def test_telegram_bot_ping_pong():
    """
    Task 0.6 Acceptance Criteria:
    'Bot answers pong in the group'
    """
    engine = AgnitiaBotEngine()
    reply = engine.handle_ping()
    assert reply == "pong", f"Expected 'pong', got '{reply}'"


def test_telegram_bot_incident_card_formatting():
    """Verifies that the bot formats incident cards with diff, root cause, and noise reduction."""
    engine = AgnitiaBotEngine()
    sample_incident = {
        "id": "INC-104",
        "status": "awaiting_approval",
        "scenario": "db_oom",
        "root_service": "postgres",
        "impacted_services": ["auth-service", "payment-service", "api-gateway", "web-ui"],
        "raw_alert_count": 56,
        "rca": {
            "root_cause": "PostgreSQL was killed for exceeding its 64Mi memory limit",
            "category": "OOMKilled",
            "confidence": 0.97,
        },
        "playbook": {
            "diff": "resources.limits.memory: 64Mi -> 256Mi",
        },
    }

    card = engine.format_incident_card(sample_incident)
    assert "INC-104" in card
    assert "PostgreSQL was killed" in card
    assert "auth-service" in card
    assert "56 alerts collapsed into 1 incident" in card
    assert "64Mi -> 256Mi" in card


def test_telegram_bot_approval_confirmation():
    """Verifies confirmation message on approval tap."""
    engine = AgnitiaBotEngine()
    msg = engine.format_approval_confirmation("INC-104", "@oncall_lead")
    assert "INC-104" in msg
    assert "@oncall_lead" in msg
    assert "APPROVED" in msg


def test_telegram_bot_rejection_notice():
    """Verifies notice message on rejection tap."""
    engine = AgnitiaBotEngine()
    msg = engine.format_rejection_notice("INC-104", "@oncall_lead")
    assert "INC-104" in msg
    assert "@oncall_lead" in msg
    assert "REJECTED" in msg
