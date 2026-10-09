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

    elif scenario_id == "cpu_spike":
        assert data["root_service"] == "auth-service", (
            f"Expected root_service 'auth-service', got '{data['root_service']}'"
        )
        assert data["duration_s"] == 12, f"Expected duration_s 12, got {data['duration_s']}"
        assert total_alerts == 24, f"Expected exactly 24 alerts for cpu_spike, got {total_alerts}"

        # Per-service breakdown: auth-service:6, api-gateway:11, web-ui:7
        expected_breakdown = {
            "auth-service": 6,
            "api-gateway":  11,
            "web-ui":       7,
        }
        for svc, expected_count in expected_breakdown.items():
            actual = counts.get(svc, 0)
            assert actual == expected_count, (
                f"Alert count mismatch for {svc}: expected {expected_count}, got {actual}"
            )
        # Healthy services must have 0 alerts
        for healthy in ["postgres", "redis", "payment-service"]:
            assert counts.get(healthy, 0) == 0, (
                f"Healthy service {healthy} must have 0 alerts, got {counts.get(healthy, 0)}"
            )

        # Alert timestamps in [5.5, 8.5]
        for a in alerts:
            t = a["t_s"]
            assert 5.5 <= t <= 8.5, f"Alert timestamp {t} out of range [5.5, 8.5]"

        # Fix action
        fix = data.get("fix", {})
        assert fix.get("action") == "patch_cpu_limit", (
            f"Expected fix action 'patch_cpu_limit', got {fix.get('action')}"
        )
        assert fix.get("from") == "250m", f"Expected fix.from '250m', got {fix.get('from')}"
        assert fix.get("to") == "1000m", f"Expected fix.to '1000m', got {fix.get('to')}"

        # Citable log line: 'CPU throttling detected' in auth-service logs
        auth_logs = data.get("logs", {}).get("auth-service", [])
        citable = next(
            (l for l in auth_logs if "CPU throttling detected" in l.get("text", "")), None
        )
        assert citable is not None, (
            "Missing citable 'CPU throttling detected' line in auth-service logs"
        )

        # Metrics: cpu_pct ramps from ~20 to ~98
        auth_metrics = data.get("metrics", {}).get("auth-service", [])
        assert len(auth_metrics) >= 10, "Expected >=10 metric points for auth-service"
        cpus = [p["cpu_pct"] for p in auth_metrics]
        assert cpus[0] < 30, f"First cpu_pct should be ~20, got {cpus[0]}"
        assert cpus[-1] > 90, f"Last cpu_pct should be ~98, got {cpus[-1]}"

    elif scenario_id == "slow_leak":
        assert data["root_service"] == "postgres", (
            f"Expected root_service 'postgres', got '{data['root_service']}'"
        )
        assert data["duration_s"] >= 240, f"Expected duration_s >= 240, got {data['duration_s']}"
        assert total_alerts == 56, f"Expected 56 alerts for slow_leak, got {total_alerts}"

        # Same per-service breakdown as db_oom
        expected_breakdown = {
            "postgres":        1,
            "auth-service":   10,
            "payment-service": 15,
            "api-gateway":    18,
            "web-ui":         12,
        }
        for svc, expected_count in expected_breakdown.items():
            actual = counts.get(svc, 0)
            assert actual == expected_count, (
                f"Alert count mismatch for {svc}: expected {expected_count}, got {actual}"
            )
        assert counts.get("redis", 0) == 0

        # No alerts before t_s 240.0
        pre_crash = [a for a in alerts if a["t_s"] < 240.0]
        assert len(pre_crash) == 0, (
            f"Expected 0 alerts before t_s=240.0, got {len(pre_crash)}: {pre_crash[:3]}"
        )

        # All post-crash alerts at t_s >= 240.2
        for a in alerts:
            assert a["t_s"] >= 240.2, f"Alert at t_s={a['t_s']} is before 240.2"

        # Metric points: ~481 (0.5s steps from 0 to 240)
        pg_metrics = data.get("metrics", {}).get("postgres", [])
        assert len(pg_metrics) >= 400, (
            f"Expected ~481 metric points for postgres, got {len(pg_metrics)}"
        )

        # Memory ramps from ~40 to ~64
        mems = [p["mem_mb"] for p in pg_metrics]
        assert mems[0] < 43, f"First mem_mb should be ~40, got {mems[0]}"
        assert mems[-1] > 60, f"Last mem_mb should be ~64, got {mems[-1]}"

        # Monotone trend: every 20-point window must have positive slope
        N = len(mems)
        for start in range(N - 20):
            window = mems[start:start+20]
            xs = list(range(20))
            xm = sum(xs) / 20
            ym = sum(window) / 20
            num = sum((xs[i]-xm)*(window[i]-ym) for i in range(20))
            den = sum((xs[i]-xm)**2 for i in range(20))
            slope_w = num / den if den else 0
            assert slope_w > 0, (
                f"Non-positive trend at window starting index {start} (t_s~{pg_metrics[start]['t_s']}s): "
                f"slope={slope_w:.6f}"
            )

        # preventive_fix_at_s hint present
        assert "preventive_fix_at_s" in data, (
            "slow_leak must have a top-level 'preventive_fix_at_s' field"
        )
        pfas = data["preventive_fix_at_s"]
        assert 60 <= pfas <= 220, f"preventive_fix_at_s {pfas} out of expected range [60, 220]"

        # Citable FATAL line in postgres logs
        pg_logs = data.get("logs", {}).get("postgres", [])
        fatal_line = next(
            (l for l in pg_logs if "FATAL: out of memory" in l.get("text", "")), None
        )
        assert fatal_line is not None, "Missing 'FATAL: out of memory' in postgres logs"

        # Fix action matches db_oom
        fix = data.get("fix", {})
        assert fix.get("action") == "patch_memory_limit", (
            f"Expected fix action 'patch_memory_limit', got {fix.get('action')}"
        )
        assert fix.get("from") == "64Mi"
        assert fix.get("to") == "256Mi"

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
        print(
            f"Total alerts: {sum(counts.values())} "
            f"(postgres: {counts['postgres']}, auth: {counts['auth-service']}, "
            f"payment: {counts['payment-service']}, gateway: {counts['api-gateway']}, ui: {counts['web-ui']})"
        )
    elif scenario_id == "cpu_spike":
        a = counts.get("auth-service", 0)
        gw = counts.get("api-gateway", 0)
        ui = counts.get("web-ui", 0)
        auth_metrics = data.get("metrics", {}).get("auth-service", [])
        cpu_peak = max((p["cpu_pct"] for p in auth_metrics), default=0)
        print("PASS")
        print(
            f"auth-service: {a}, api-gateway: {gw}, web-ui: {ui} ({a}/{gw}/{ui}) "
            f"| cpu_peak: {cpu_peak}%"
        )
    elif scenario_id == "slow_leak":
        pg_metrics = data.get("metrics", {}).get("postgres", [])
        mem_start = pg_metrics[0]["mem_mb"] if pg_metrics else "?"
        mem_end = pg_metrics[-1]["mem_mb"] if pg_metrics else "?"
        pfas = data.get("preventive_fix_at_s", "?")
        print("PASS")
        print(
            f"Total alerts: {sum(counts.values())} (all post-crash t_s>=240.2) "
            f"| metrics: {len(pg_metrics)} pts, mem {mem_start}->{mem_end} MB "
            f"| preventive_fix_at_s: {pfas} "
            f"| trend: monotone in every 20-point window"
        )
    else:
        print("PASS")
        print(f"Total alerts: {sum(counts.values())}")


if __name__ == "__main__":
    main()
