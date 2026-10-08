#!/usr/bin/env python3
"""
Validation and Alert Count Script for Agnitia Scenario Datasets
Owner: Member 4 (Integrations & Content)
Task: 0.5 — Validate db_oom.json and count alerts (Must print 56)
"""

import json
import sys
from pathlib import Path
from collections import Counter


def validate_and_count(scenario_path: Path, verbose: bool = False) -> int:
    if not scenario_path.exists():
        print(f"Error: Scenario file not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)

    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Basic schema validation
    required_keys = ["id", "title", "root_service", "duration_s", "metrics", "events", "logs", "alerts", "fix"]
    for k in required_keys:
        if k not in data:
            print(f"Validation Error: Missing required key '{k}'", file=sys.stderr)
            sys.exit(1)

    assert data["id"] == "db_oom", f"Expected id 'db_oom', got '{data['id']}'"
    assert data["root_service"] == "postgres", f"Expected root_service 'postgres', got '{data['root_service']}'"
    assert data["duration_s"] == 12, f"Expected duration_s 12, got {data['duration_s']}"

    # 2. Metrics curve validation (postgres ramps to 64Mi)
    pg_metrics = data["metrics"].get("postgres", [])
    assert len(pg_metrics) >= 10, "Postgres metrics curve must contain at least 10 data points"
    assert pg_metrics[-1]["mem_mb"] == 64.0, f"Peak memory must hit 64.0Mi, got {pg_metrics[-1]['mem_mb']}"

    # 3. K8s Events validation
    oom_events = [
        e for e in data["events"]
        if "OOMKilled" in e.get("text", "") and "137" in e.get("text", "")
    ]
    assert len(oom_events) >= 1, "Must contain OOMKilled exit code 137 event"

    # 4. Logs validation (line 42 citation match)
    pg_logs = data["logs"].get("postgres", [])
    assert len(pg_logs) >= 42, "Postgres logs must contain at least 42 lines"
    line_42 = next((l for l in pg_logs if l.get("line") == 42), None)
    assert line_42 is not None and "out of memory" in line_42.get("text", "").lower(), (
        "Log line 42 must contain 'FATAL: out of memory' citation"
    )

    # 5. Fix definition
    fix = data["fix"]
    assert fix.get("action") == "patch_memory_limit", "Fix action must be 'patch_memory_limit'"
    assert fix.get("to") == "256Mi", "Fix memory target must be '256Mi'"

    # 6. Exact 56 Alerts validation (CONTRACT.md Section 1 breakdown)
    alerts = data.get("alerts", [])
    total_alerts = len(alerts)
    counts = Counter(a["service"] for a in alerts)

    expected_breakdown = {
        "postgres": 1,
        "auth-service": 10,
        "payment-service": 15,
        "api-gateway": 18,
        "web-ui": 12,
    }

    for svc, expected_count in expected_breakdown.items():
        actual = counts.get(svc, 0)
        assert actual == expected_count, (
            f"Alert count mismatch for {svc}: expected {expected_count}, got {actual}"
        )

    # Redis must be completely healthy (0 alerts)
    assert counts.get("redis", 0) == 0, "Redis must have 0 alerts (healthy node)"

    if verbose:
        print("=" * 60)
        print("  AGNITIA SCENARIO DATASET VALIDATION (Member 4)")
        print("=" * 60)
        print(f"Scenario ID      : {data['id']}")
        print(f"Title            : {data['title']}")
        print(f"Root Service     : {data['root_service']}")
        print(f"Duration         : {data['duration_s']}s")
        print(f"Postgres Metrics : {len(pg_metrics)} curve points (40Mi -> 64Mi)")
        print(f"Postgres Logs    : {len(pg_logs)} lines (Line 42: {line_42['text']})")
        print(f"K8s Events       : {len(data['events'])} events ({oom_events[0]['text']})")
        print(f"Remediation Fix  : {fix['action']} ({fix.get('from')} -> {fix.get('to')})")
        print("-" * 60)
        print("Alert Breakdown (Graph Correlation Proof):")
        for svc, count in expected_breakdown.items():
            role = "Root Cause" if svc == "postgres" else "Impacted Victim"
            print(f"  • {svc:<18}: {count:>2} alerts [{role}]")
        print(f"  • {'redis':<18}:  0 alerts [Healthy / Excluded]")
        print("-" * 60)
        print(f"Total Collapsed Alerts: {total_alerts}")
        print("Status: VALIDATION PASSED (100% Contract Compliant)")
        print("=" * 60)

    return total_alerts


def main():
    repo_root = Path(__file__).resolve().parent.parent
    scenario_path = repo_root / "backend" / "scenarios" / "db_oom.json"

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    count = validate_and_count(scenario_path, verbose=verbose)

    # Done criteria: "a count script prints 56"
    print(count)


if __name__ == "__main__":
    main()
