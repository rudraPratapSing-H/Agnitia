#!/usr/bin/env python3
"""
Build Mock Event Stream for Agnitia Checkpoint 1 / Member 1 UI Replay
Owner: Member 4 (Integrations & Content)
Task: 1.4 — Generate frontend/src/mock/events_db_oom.json from backend/scenarios/db_oom.json

Stream sequence:
1. reset event, then service_update events for all 6 services as healthy
2. metric_point events for postgres every 0.5 s during memory ramp
3. At t_s 6.0, service_update: postgres status root_cause
4. All 56 alert events at scenario times (incident_id="INC-104"), plus service_update impacted
   for auth-service, payment-service, api-gateway, and web-ui on their first alert. Redis never changes.
5. incident_update: id INC-104, status detected, raw_alert_count 56, started_at=first alert time
6. Six agent_step events (running, done) about 1 s apart:
   - triage (grouping 56 alerts by dependency graph)
   - diagnose (reading last 50 log lines from postgres-0)
   - diagnose (found OOMKilled, Exit Code 137)
   - diagnose (memory 63.8Mi of 64Mi limit)
   - plan (database before dependants)
   - verify (all citations match raw logs)
7. incident_update: status awaiting_approval with full RCA & Playbook matching CONTRACT.md
8. Tail: 3 s after approval moment, incident_update healing, playbook_step running/done for all 5 steps,
   service_update recovering then healthy in playbook order, then incident_update resolved
   with resolved_at about 38 s after started_at.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIO_PATH = REPO_ROOT / "backend" / "scenarios" / "db_oom.json"
OUTPUT_PATH = REPO_ROOT / "frontend" / "src" / "mock" / "events_db_oom.json"

BASE_TIME = datetime(2026, 10, 9, 3, 14, 0, tzinfo=timezone.utc)

DEFAULT_SERVICES: Dict[str, dict] = {
    "web-ui": {
        "label": "Web UI",
        "tier": "frontend",
        "depends_on": ["api-gateway"],
        "metrics": {"mem_mb": 42.0, "mem_limit_mb": 128.0, "cpu_pct": 5.0, "restarts": 0},
    },
    "api-gateway": {
        "label": "API Gateway",
        "tier": "edge",
        "depends_on": ["auth-service", "payment-service"],
        "metrics": {"mem_mb": 65.0, "mem_limit_mb": 128.0, "cpu_pct": 14.0, "restarts": 0},
    },
    "auth-service": {
        "label": "Auth Service",
        "tier": "backend",
        "depends_on": ["postgres", "redis"],
        "metrics": {"mem_mb": 50.0, "mem_limit_mb": 128.0, "cpu_pct": 8.0, "restarts": 0},
    },
    "payment-service": {
        "label": "Payment Service",
        "tier": "backend",
        "depends_on": ["postgres"],
        "metrics": {"mem_mb": 72.0, "mem_limit_mb": 128.0, "cpu_pct": 11.0, "restarts": 0},
    },
    "redis": {
        "label": "Redis Cache",
        "tier": "data",
        "depends_on": [],
        "metrics": {"mem_mb": 24.0, "mem_limit_mb": 64.0, "cpu_pct": 3.0, "restarts": 0},
    },
    "postgres": {
        "label": "PostgreSQL",
        "tier": "data",
        "depends_on": [],
        "metrics": {"mem_mb": 58.0, "mem_limit_mb": 64.0, "cpu_pct": 12.0, "restarts": 0},
    },
}


def format_iso(dt: datetime) -> str:
    """Formats datetime to ISO 8601 UTC string with millisecond precision."""
    ms = int(dt.microsecond / 1000)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def build_mock_events() -> List[Dict[str, Any]]:
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        scenario_data = json.load(f)

    events: List[Dict[str, Any]] = []
    current_t_s = -0.01

    def add_event(event_type: str, payload: dict, target_t_s: float):
        nonlocal current_t_s
        # Guarantee strictly increasing timestamps: at least 5 milliseconds forward
        if target_t_s <= current_t_s:
            target_t_s = round(current_t_s + 0.005, 4)
        current_t_s = target_t_s
        dt = BASE_TIME + timedelta(seconds=current_t_s)
        events.append({
            "type": event_type,
            "ts": format_iso(dt),
            "payload": payload,
        })

    # =========================================================================
    # 1. Reset event, then service_update events for all 6 services as healthy
    # =========================================================================
    add_event("reset", {}, target_t_s=0.0)

    # Initial topology emission
    svc_order = ["postgres", "redis", "auth-service", "payment-service", "api-gateway", "web-ui"]
    for i, s_id in enumerate(svc_order):
        s_data = DEFAULT_SERVICES[s_id]
        payload = {
            "id": s_id,
            "label": s_data["label"],
            "tier": s_data["tier"],
            "depends_on": s_data["depends_on"],
            "status": "healthy",
            "metrics": {
                "mem_mb": 40.0 if s_id == "postgres" else s_data["metrics"]["mem_mb"],
                "mem_limit_mb": s_data["metrics"]["mem_limit_mb"],
                "cpu_pct": s_data["metrics"]["cpu_pct"],
                "restarts": 0,
            },
        }
        add_event("service_update", payload, target_t_s=0.02 * (i + 1))

    # =========================================================================
    # 2. metric_point events for postgres every 0.5 s during ramp
    # =========================================================================
    pg_points = scenario_data.get("metrics", {}).get("postgres", [])
    for pt in pg_points:
        t_val = float(pt["t_s"])
        if t_val < 6.0 and t_val > 0.0:
            add_event(
                "metric_point",
                {
                    "service": "postgres",
                    "t_s": t_val,
                    "mem_mb": float(pt["mem_mb"]),
                    "cpu_pct": float(pt["cpu_pct"]),
                },
                target_t_s=t_val,
            )

    # =========================================================================
    # 3. At t_s 6.0: postgres status root_cause (and peak metric point)
    # =========================================================================
    add_event(
        "metric_point",
        {
            "service": "postgres",
            "t_s": 6.0,
            "mem_mb": 64.0,
            "cpu_pct": 42.0,
        },
        target_t_s=6.0,
    )

    pg_root = {
        "id": "postgres",
        "label": "PostgreSQL",
        "tier": "data",
        "depends_on": [],
        "status": "root_cause",
        "metrics": {
            "mem_mb": 64.0,
            "mem_limit_mb": 64.0,
            "cpu_pct": 42.0,
            "restarts": 0,
        },
    }
    add_event("service_update", pg_root, target_t_s=6.01)

    # =========================================================================
    # 4. All 56 alert events at scenario times with incident_id="INC-104"
    #    When the first alert of each downstream service arrives, emit service_update
    #    with status impacted for auth-service, payment-service, api-gateway, and web-ui.
    #    Redis never changes.
    # =========================================================================
    raw_alerts = scenario_data.get("alerts", [])
    impacted_services_set = {"auth-service", "payment-service", "api-gateway", "web-ui"}
    impacted_emitted = set()

    first_alert_ts_str = ""

    for alert in raw_alerts:
        a_svc = alert["service"]
        a_ts = float(alert.get("t_s", 6.2))

        # Check if downstream service is alerted for the first time
        if a_svc in impacted_services_set and a_svc not in impacted_emitted:
            impacted_emitted.add(a_svc)
            s_data = DEFAULT_SERVICES[a_svc]
            imp_payload = {
                "id": a_svc,
                "label": s_data["label"],
                "tier": s_data["tier"],
                "depends_on": s_data["depends_on"],
                "status": "impacted",
                "metrics": {
                    "mem_mb": s_data["metrics"]["mem_mb"],
                    "mem_limit_mb": s_data["metrics"]["mem_limit_mb"],
                    "cpu_pct": s_data["metrics"]["cpu_pct"],
                    "restarts": 0,
                },
            }
            add_event("service_update", imp_payload, target_t_s=a_ts - 0.005)

        # Emit the alert event
        alert_payload = {
            "id": alert["id"],
            "ts": format_iso(BASE_TIME + timedelta(seconds=max(a_ts, current_t_s + 0.005))),
            "service": a_svc,
            "severity": alert["severity"],
            "message": alert["message"],
            "incident_id": "INC-104",
        }
        add_event("alert", alert_payload, target_t_s=a_ts)

        if not first_alert_ts_str:
            first_alert_ts_str = events[-1]["ts"]

    # =========================================================================
    # 5. Right after the last alert: incident_update status detected
    # =========================================================================
    inc_detected = {
        "id": "INC-104",
        "status": "detected",
        "scenario": "db_oom",
        "root_service": "postgres",
        "impacted_services": ["auth-service", "payment-service", "api-gateway", "web-ui"],
        "raw_alert_count": 56,
        "started_at": first_alert_ts_str,
        "resolved_at": None,
        "rca": None,
        "playbook": None,
        "timeline": [
            {"t_s": 0.0, "event": "First alert received: 56 alerts collapsed into INC-104"}
        ],
    }
    add_event("incident_update", inc_detected, target_t_s=current_t_s + 0.1)

    # =========================================================================
    # 6. Six agent_step events, about 1 s apart, status running then done
    # =========================================================================
    agent_steps = [
        ("triage", "Grouping 56 alerts by dependency graph; identifying root candidate"),
        ("diagnose", "Reading last 50 log lines from postgres-0 container telemetry"),
        ("diagnose", "Found container lifecycle termination: Reason: OOMKilled, Exit Code: 137"),
        ("diagnose", "Memory curve analysis confirmed: memory peaked at 63.8Mi of 64Mi limit"),
        ("plan", "Synthesizing ordered recovery sequence: database before dependants"),
        ("verify", "Cross-referencing evidence citations: all citations match raw logs"),
    ]

    base_agent_t_s = max(current_t_s + 0.5, 8.5)
    for idx, (agent_name, text) in enumerate(agent_steps):
        step_start_t = base_agent_t_s + (idx * 1.0)
        # Running event
        add_event(
            "agent_step",
            {"agent": agent_name, "text": f"{text}...", "status": "running"},
            target_t_s=step_start_t,
        )
        # Done event ~0.4s later
        add_event(
            "agent_step",
            {"agent": agent_name, "text": text, "status": "done"},
            target_t_s=step_start_t + 0.4,
        )

    # =========================================================================
    # 7. incident_update with status awaiting_approval carrying full RCA & playbook
    # =========================================================================
    inc_awaiting = {
        "id": "INC-104",
        "status": "awaiting_approval",
        "scenario": "db_oom",
        "root_service": "postgres",
        "impacted_services": ["auth-service", "payment-service", "api-gateway", "web-ui"],
        "raw_alert_count": 56,
        "started_at": first_alert_ts_str,
        "resolved_at": None,
        "rca": {
            "root_cause": "PostgreSQL was killed for exceeding its 64Mi memory limit",
            "category": "OOMKilled",
            "confidence": 0.97,
            "evidence": [
                {
                    "type": "k8s_event",
                    "source": "postgres-0",
                    "line": None,
                    "text": "Reason: OOMKilled, Exit Code: 137",
                    "verified": True,
                },
                {
                    "type": "log",
                    "source": "postgres-0",
                    "line": 42,
                    "text": "FATAL: out of memory",
                    "verified": True,
                },
                {
                    "type": "metric",
                    "source": "postgres-0",
                    "line": None,
                    "text": "memory 63.8Mi of 64Mi limit at 03:14:05",
                    "verified": True,
                },
            ],
            "similar_incident": {"id": "INC-087", "similarity": 0.94},
        },
        "playbook": {
            "diff": "resources.limits.memory: 64Mi -> 256Mi",
            "steps": [
                {
                    "order": 1,
                    "service": "postgres",
                    "action": "patch_memory_limit",
                    "params": {"from": "64Mi", "to": "256Mi"},
                    "risk": "high",
                    "requires_approval": True,
                    "verify": "port 5432 accepting connections",
                },
                {
                    "order": 2,
                    "service": "postgres",
                    "action": "wait_for_ready",
                    "params": {"timeout_s": 30},
                    "risk": "low",
                    "requires_approval": False,
                    "verify": "readiness probe passes",
                },
                {
                    "order": 3,
                    "service": "auth-service",
                    "action": "rollout_restart",
                    "params": {},
                    "risk": "low",
                    "requires_approval": False,
                    "verify": "health endpoint 200",
                },
                {
                    "order": 4,
                    "service": "payment-service",
                    "action": "rollout_restart",
                    "params": {},
                    "risk": "low",
                    "requires_approval": False,
                    "verify": "health endpoint 200",
                },
                {
                    "order": 5,
                    "service": "api-gateway",
                    "action": "verify_health",
                    "params": {},
                    "risk": "low",
                    "requires_approval": False,
                    "verify": "error rate below 1%",
                },
            ],
        },
        "timeline": [
            {"t_s": 0.0, "event": "First alert received: alert storm detected"},
            {"t_s": 2.5, "event": "Root cause isolated to postgres via dependency graph"},
            {"t_s": 6.5, "event": "Root cause verified with citations; playbook synthesized"},
            {"t_s": 8.5, "event": "Awaiting human authorization for high-risk memory patch"},
        ],
    }
    awaiting_t_s = max(current_t_s + 0.5, 15.0)
    add_event("incident_update", inc_awaiting, target_t_s=awaiting_t_s)

    # =========================================================================
    # 8. Tail: 3 s after approval moment:
    #    playbook_step events for each of the 5 steps (running, done)
    #    service_update recovering then healthy in playbook order:
    #    postgres, auth-service, payment-service, api-gateway, web-ui
    #    incident_update healing then resolved with resolved_at about 38 s after started_at
    # =========================================================================
    approval_moment_t_s = awaiting_t_s + 2.0  # human approves at t_s ~17s
    exec_start_t_s = approval_moment_t_s + 3.0  # 3s after approval moment -> ~20s

    # Incident status transitions to healing
    inc_healing = dict(inc_awaiting)
    inc_healing["status"] = "healing"
    add_event("incident_update", inc_healing, target_t_s=exec_start_t_s)

    # Step 1: postgres patch_memory_limit
    t_cursor = exec_start_t_s + 0.5
    add_event(
        "playbook_step",
        {"order": 1, "service": "postgres", "status": "running", "action": "patch_memory_limit"},
        target_t_s=t_cursor,
    )
    t_cursor += 1.0
    pg_recovering = dict(pg_root)
    pg_recovering["status"] = "recovering"
    pg_recovering["metrics"]["mem_limit_mb"] = 256.0
    add_event("service_update", pg_recovering, target_t_s=t_cursor)
    t_cursor += 0.5
    add_event(
        "playbook_step",
        {"order": 1, "service": "postgres", "status": "done", "action": "patch_memory_limit"},
        target_t_s=t_cursor,
    )

    # Step 2: postgres wait_for_ready -> becomes healthy
    t_cursor += 1.0
    add_event(
        "playbook_step",
        {"order": 2, "service": "postgres", "status": "running", "action": "wait_for_ready"},
        target_t_s=t_cursor,
    )
    t_cursor += 1.0
    pg_healthy = dict(pg_recovering)
    pg_healthy["status"] = "healthy"
    add_event("service_update", pg_healthy, target_t_s=t_cursor)
    t_cursor += 0.5
    add_event(
        "playbook_step",
        {"order": 2, "service": "postgres", "status": "done", "action": "wait_for_ready"},
        target_t_s=t_cursor,
    )

    # Step 3: auth-service rollout_restart
    t_cursor += 1.0
    add_event(
        "playbook_step",
        {"order": 3, "service": "auth-service", "status": "running", "action": "rollout_restart"},
        target_t_s=t_cursor,
    )
    t_cursor += 1.0
    auth_rec = dict(DEFAULT_SERVICES["auth-service"])
    auth_rec["id"] = "auth-service"
    auth_rec["status"] = "recovering"
    add_event("service_update", auth_rec, target_t_s=t_cursor)
    t_cursor += 1.0
    auth_rec["status"] = "healthy"
    add_event("service_update", auth_rec, target_t_s=t_cursor)
    t_cursor += 0.5
    add_event(
        "playbook_step",
        {"order": 3, "service": "auth-service", "status": "done", "action": "rollout_restart"},
        target_t_s=t_cursor,
    )

    # Step 4: payment-service rollout_restart
    t_cursor += 1.0
    add_event(
        "playbook_step",
        {"order": 4, "service": "payment-service", "status": "running", "action": "rollout_restart"},
        target_t_s=t_cursor,
    )
    t_cursor += 1.0
    pay_rec = dict(DEFAULT_SERVICES["payment-service"])
    pay_rec["id"] = "payment-service"
    pay_rec["status"] = "recovering"
    add_event("service_update", pay_rec, target_t_s=t_cursor)
    t_cursor += 1.0
    pay_rec["status"] = "healthy"
    add_event("service_update", pay_rec, target_t_s=t_cursor)
    t_cursor += 0.5
    add_event(
        "playbook_step",
        {"order": 4, "service": "payment-service", "status": "done", "action": "rollout_restart"},
        target_t_s=t_cursor,
    )

    # Step 5: api-gateway verify_health, then web-ui recovers
    t_cursor += 1.0
    add_event(
        "playbook_step",
        {"order": 5, "service": "api-gateway", "status": "running", "action": "verify_health"},
        target_t_s=t_cursor,
    )
    t_cursor += 1.0
    gw_rec = dict(DEFAULT_SERVICES["api-gateway"])
    gw_rec["id"] = "api-gateway"
    gw_rec["status"] = "recovering"
    add_event("service_update", gw_rec, target_t_s=t_cursor)
    t_cursor += 1.0
    gw_rec["status"] = "healthy"
    add_event("service_update", gw_rec, target_t_s=t_cursor)

    # web-ui recovers
    t_cursor += 0.5
    ui_rec = dict(DEFAULT_SERVICES["web-ui"])
    ui_rec["id"] = "web-ui"
    ui_rec["status"] = "recovering"
    add_event("service_update", ui_rec, target_t_s=t_cursor)
    t_cursor += 1.0
    ui_rec["status"] = "healthy"
    add_event("service_update", ui_rec, target_t_s=t_cursor)

    t_cursor += 0.5
    add_event(
        "playbook_step",
        {"order": 5, "service": "api-gateway", "status": "done", "action": "verify_health"},
        target_t_s=t_cursor,
    )

    # Incident resolved: resolved_at is about 38 s after started_at
    # started_at corresponds to first alert (~6.0s), so resolved_at is at 6.0 + 38.0 = 44.0s
    resolved_t_s = max(t_cursor + 1.0, 44.0)
    resolved_dt = BASE_TIME + timedelta(seconds=resolved_t_s)
    resolved_ts_str = format_iso(resolved_dt)

    inc_resolved = dict(inc_awaiting)
    inc_resolved["status"] = "resolved"
    inc_resolved["resolved_at"] = resolved_ts_str
    inc_resolved["timeline"].append({
        "t_s": 38.0,
        "event": "Automated playbook execution complete: all 6 microservices healthy (MTTR: 38s)",
    })
    add_event("incident_update", inc_resolved, target_t_s=resolved_t_s)

    return events


def main():
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    events = build_mock_events()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)
    print(f"Generated {len(events)} mock events in frontend/src/mock/events_db_oom.json")



if __name__ == "__main__":
    main()
