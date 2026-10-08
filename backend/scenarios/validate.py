#!/usr/bin/env python3
"""
Scenario Validation Script for Agnitia
Validates scenario datasets against CONTRACT.md schema and scenario rules.
Supports db_oom.json (56 alerts), bad_config.json (31 alerts: 8/14/9), and arbitrary scenarios.

Usage:
    python validate.py [scenario_name_or_path] [--verbose]
"""

import json
import sys
from collections import Counter
from pathlib import Path


def validate_scenario(scenario_path: Path, verbose: bool = False) -> tuple[bool, Counter, dict]:
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

    scenario_id = data["id"]
    alerts = data.get("alerts", [])
    total_alerts = len(alerts)
    counts = Counter(a["service"] for a in alerts)

    # 2. Scenario-specific validations
    if scenario_id == "bad_config":
        assert data["root_service"] == "payment-service", f"Expected root_service 'payment-service', got '{data['root_service']}'"
        assert data["duration_s"] == 12, f"Expected duration_s 12, got {data['duration_s']}"
        assert total_alerts == 31, f"Expected exactly 31 alerts for bad_config, got {total_alerts}"

        # Per-service breakdown: payment-service: 8, api-gateway: 14, web-ui: 9
        expected_breakdown = {
            "payment-service": 8,
            "api-gateway": 14,
            "web-ui": 9,
        }
        for svc, expected_count in expected_breakdown.items():
            actual = counts.get(svc, 0)
            assert actual == expected_count, (
                f"Alert count mismatch for {svc}: expected {expected_count}, got {actual}"
            )

        # Unaffected services must stay healthy (0 alerts)
        for healthy_svc in ["auth-service", "postgres", "redis"]:
            assert counts.get(healthy_svc, 0) == 0, f"Expected 0 alerts for {healthy_svc}, got {counts.get(healthy_svc, 0)}"

        # Check alert timestamps between 5.0 and 8.5
        for a in alerts:
            t = a["t_s"]
            assert 5.0 <= t <= 8.5, f"Alert timestamp {t} out of range [5.0, 8.5]"
            assert a["id"].startswith("a-"), f"Alert id {a['id']} does not have stable format 'a-xxx'"

        # Distinct realistic alert messages
        messages = [a["message"] for a in alerts]
        assert any("CrashLoopBackOff" in m for m in messages), "Expected CrashLoopBackOff alert message"
        assert any("readiness probe" in m.lower() for m in messages), "Expected readiness probe failure alert message"
        assert any("503" in m for m in messages), "Expected 503 alert message"
        assert any("checkout" in m.lower() for m in messages), "Expected checkout failure alert message"

        # K8s events for payment-service
        events = data.get("events", [])
        assert len(events) >= 4, "Expected at least 4 Kubernetes events"
        event_texts = " ".join(e["text"] for e in events if e.get("service") == "payment-service")
        assert "Started" in event_texts, "Events must include 'Started'"
        assert "Back-off restarting failed container" in event_texts, "Events must include 'Back-off restarting failed container'"
        assert "Reason: Error" in event_texts, "Events must include 'Reason: Error'"
        assert "Exit Code: 1" in event_texts, "Events must include 'Exit Code: 1'"

        # Logs: ~50 lines per service, payment-service shows config error and stack trace
        ps_logs = data.get("logs", {}).get("payment-service", [])
        assert len(ps_logs) >= 45, f"Expected ~50 lines for payment-service logs, got {len(ps_logs)}"

        # Fixed, citable line number with config error
        citable_line = next(
            (l for l in ps_logs if "config error: invalid value for PAYMENT_TIMEOUT_MS: 'abc'" in l.get("text", "")),
            None
        )
        assert citable_line is not None, "Missing config error: invalid value for PAYMENT_TIMEOUT_MS: 'abc' in payment-service logs"
        citable_line_num = citable_line.get("line")
        assert citable_line_num is not None, "Citable line must have a line number"

        # Stack trace exit check
        log_texts = " ".join(l.get("text", "") for l in ps_logs)
        assert "Traceback" in log_texts or "ValueError" in log_texts, "Logs must include stack-trace-style exit"

        # Metrics: memory low and flat, cpu spiking at restarts
        ps_metrics = data.get("metrics", {}).get("payment-service", [])
        assert len(ps_metrics) >= 10, "Expected metrics curve points for payment-service"
        for pt in ps_metrics:
            assert pt["mem_mb"] < 100.0, "payment-service memory should be low and flat"

        # Fix action
        fix = data.get("fix", {})
        assert fix.get("action") == "rollback_deployment", f"Expected fix action 'rollback_deployment', got {fix.get('action')}"
        assert fix.get("from") == "payment-service:rev-7", f"Expected fix from 'payment-service:rev-7', got {fix.get('from')}"
        assert fix.get("to") == "payment-service:rev-6", f"Expected fix to 'payment-service:rev-6', got {fix.get('to')}"

    elif scenario_id == "db_oom":
        assert data["root_service"] == "postgres", f"Expected root_service 'postgres', got '{data['root_service']}'"
        assert total_alerts == 56, f"Expected 56 alerts for db_oom, got {total_alerts}"
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
        assert counts.get("redis", 0) == 0

    return True, counts, data


def main():
    if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    repo_root = Path(__file__).resolve().parent.parent.parent
    scenarios_dir = Path(__file__).resolve().parent

    # Determine target scenario
    target = None
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    if args:
        candidate = Path(args[0])
        if candidate.exists():
            target = candidate
        elif (scenarios_dir / args[0]).exists():
            target = scenarios_dir / args[0]
        elif (scenarios_dir / f"{args[0]}.json").exists():
            target = scenarios_dir / f"{args[0]}.json"
        else:
            print(f"Error: Cannot find scenario '{args[0]}'", file=sys.stderr)
            sys.exit(1)
    else:
        # Default to bad_config.json
        target = scenarios_dir / "bad_config.json"

    ok, counts, data = validate_scenario(target, verbose=verbose)

    scenario_id = data["id"]
    if scenario_id == "bad_config":
        # Required output: "validate.py prints PASS and the per-service counts 8/14/9"
        ps = counts.get("payment-service", 0)
        gw = counts.get("api-gateway", 0)
        ui = counts.get("web-ui", 0)
        print("PASS")
        print(f"payment-service: {ps}, api-gateway: {gw}, web-ui: {ui} ({ps}/{gw}/{ui})")
    elif scenario_id == "db_oom":
        print("PASS")
        print(f"Total alerts: {sum(counts.values())} (postgres: {counts['postgres']}, auth: {counts['auth-service']}, payment: {counts['payment-service']}, gateway: {counts['api-gateway']}, ui: {counts['web-ui']})")
    else:
        print("PASS")
        print(f"Total alerts: {sum(counts.values())}")


if __name__ == "__main__":
    main()
