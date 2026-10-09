#!/usr/bin/env python3
"""
Generator script for bad_config.json scenario.
Scenario: payment-service enters a crash loop after a bad config push (PAYMENT_TIMEOUT_MS="abc" fails to parse).
Task 1.12 - Agnitia
"""

import json
import sys
from pathlib import Path


def generate_bad_config() -> dict:
    # 1. Metrics for payment-service
    # Memory stays low and flat (~72MB), CPU spikes briefly during boot/crashes.
    # Restarts count up from 0 to 4.
    metrics = {"payment-service": []}
    restarts_schedule = [
        (0.0, 4.5, 0, 4.5, 71.5),
        (5.0, 5.0, 1, 38.0, 72.0),
        (5.5, 6.0, 1, 6.0, 72.0),
        (6.2, 6.2, 2, 42.0, 72.2),
        (6.5, 7.0, 2, 7.5, 72.1),
        (7.4, 7.4, 3, 44.5, 72.3),
        (7.5, 8.0, 3, 8.0, 72.0),
        (8.5, 8.5, 4, 41.0, 72.2),
        (9.0, 12.0, 4, 3.5, 71.8),
    ]

    time_points = [
        0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5,
        5.0, 5.5, 6.0, 6.2, 6.5, 7.0, 7.4, 7.5, 8.0, 8.5,
        9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0
    ]

    for t in time_points:
        # Determine restart count, cpu and mem
        if t < 5.0:
            restarts = 0
            cpu = 4.8 + (t % 1.0) * 0.5
            mem = 71.5 + (t % 1.0) * 0.3
        elif t == 5.0:
            restarts = 1
            cpu = 38.5
            mem = 72.0
        elif t < 6.2:
            restarts = 1
            cpu = 6.2
            mem = 71.9
        elif t == 6.2:
            restarts = 2
            cpu = 42.0
            mem = 72.2
        elif t < 7.4:
            restarts = 2
            cpu = 7.1
            mem = 72.0
        elif t == 7.4:
            restarts = 3
            cpu = 44.0
            mem = 72.4
        elif t < 8.5:
            restarts = 3
            cpu = 7.8
            mem = 72.1
        elif t == 8.5:
            restarts = 4
            cpu = 41.5
            mem = 72.3
        else:
            restarts = 4
            cpu = 3.2
            mem = 71.6

        metrics["payment-service"].append({
            "t_s": round(t, 2),
            "mem_mb": round(mem, 1),
            "cpu_pct": round(cpu, 1),
            "restarts": restarts
        })

    # 2. Kubernetes Pod Events
    events = [
        {
            "t_s": 4.8,
            "service": "payment-service",
            "text": "Started container payment-service (deployment revision 7)"
        },
        {
            "t_s": 5.0,
            "service": "payment-service",
            "text": "Reason: Error, Exit Code: 1 (container payment-service terminated unexpectedly)"
        },
        {
            "t_s": 5.2,
            "service": "payment-service",
            "text": "Back-off restarting failed container: CrashLoopBackOff (restart count: 1)"
        },
        {
            "t_s": 6.0,
            "service": "payment-service",
            "text": "Started container payment-service (pod payment-service-7f49c8dbb6-q8x2m)"
        },
        {
            "t_s": 6.2,
            "service": "payment-service",
            "text": "Reason: Error, Exit Code: 1 (container payment-service terminated unexpectedly)"
        },
        {
            "t_s": 6.4,
            "service": "payment-service",
            "text": "Back-off restarting failed container: CrashLoopBackOff (restart count: 2)"
        },
        {
            "t_s": 7.2,
            "service": "payment-service",
            "text": "Started container payment-service (pod payment-service-7f49c8dbb6-q8x2m)"
        },
        {
            "t_s": 7.4,
            "service": "payment-service",
            "text": "Reason: Error, Exit Code: 1 (container payment-service terminated unexpectedly)"
        },
        {
            "t_s": 7.6,
            "service": "payment-service",
            "text": "Back-off restarting failed container: CrashLoopBackOff (restart count: 3)"
        },
        {
            "t_s": 8.3,
            "service": "payment-service",
            "text": "Started container payment-service (pod payment-service-7f49c8dbb6-q8x2m)"
        },
        {
            "t_s": 8.5,
            "service": "payment-service",
            "text": "Reason: Error, Exit Code: 1 (container payment-service terminated unexpectedly)"
        },
        {
            "t_s": 8.6,
            "service": "payment-service",
            "text": "Back-off restarting failed container: CrashLoopBackOff (restart count: 4)"
        }
    ]

    # 3. Exactly 31 Alerts between t_s 5.0 and 8.5
    # payment-service: 8
    # api-gateway: 14
    # web-ui: 9
    # auth-service: 0, postgres: 0, redis: 0
    raw_alerts = [
        # t_s 5.0: Initial failure on payment-service
        (5.0, "payment-service", "critical", "Pod CrashLoopBackOff: container payment-service terminated with exit code 1"),
        (5.1, "payment-service", "error", "Readiness probe failed: HTTP 500 connection refused on :8082/ready"),
        # t_s 5.2 - 5.5: Upstream api-gateway notices connection refusal, web-ui starts failing checkout
        (5.2, "api-gateway", "error", "503 Service Unavailable: upstream payment-service:8082 connection refused"),
        (5.3, "api-gateway", "error", "Upstream connection failure: dial tcp 10.244.1.42:8082: connect: connection refused"),
        (5.4, "web-ui", "error", "Checkout failed: 503 Service Unavailable returned from api-gateway on /api/v1/checkout"),
        (5.5, "api-gateway", "warning", "Upstream request timeout: payment-service failed to respond within 2000ms"),
        (5.6, "web-ui", "error", "User transaction error: checkout failed for session #9412 due to payment service outage"),
        (5.7, "payment-service", "warning", "Container payment-service restart count 1 threshold exceeded"),
        (5.8, "api-gateway", "critical", "Circuit breaker tripped: payment-service consecutive connection failures > 5"),
        (5.9, "web-ui", "warning", "Payment modal error: 'Payment gateway unavailable, please try again later'"),
        # t_s 6.0 - 6.5: Restart 2 fails, cascade worsens
        (6.1, "payment-service", "error", "Liveness probe failed: container failed health check on :8082/healthz"),
        (6.2, "payment-service", "critical", "Pod CrashLoopBackOff: Back-off 20s restarting failed container payment-service"),
        (6.3, "api-gateway", "error", "503 Service Unavailable: upstream payment-service unhealthy on route /api/v1/payments"),
        (6.4, "api-gateway", "critical", "Circuit breaker open: fast-failing traffic to payment-service"),
        (6.5, "web-ui", "critical", "Checkout error rate spike: 28% of customer checkout attempts failing"),
        (6.6, "api-gateway", "error", "HTTP 503 rate spike: 35.4% error rate on /api/v1/payments/process"),
        (6.8, "web-ui", "error", "Checkout failed: payment confirmation RPC rejected by upstream gateway"),
        (6.9, "api-gateway", "error", "Upstream connection reset: socket closed by peer on payment-service:8082"),
        (7.0, "payment-service", "warning", "Container payment-service restart count 2 threshold exceeded"),
        (7.1, "api-gateway", "error", "503 Service Unavailable: no healthy upstream instances in payment cluster"),
        # t_s 7.2 - 7.8: Restart 3 fails
        (7.3, "payment-service", "error", "Readiness probe failed: Get http://10.244.1.42:8082/ready: dial tcp connect refused"),
        (7.4, "payment-service", "critical", "Pod CrashLoopBackOff: Back-off 40s restarting failed container payment-service"),
        (7.5, "api-gateway", "critical", "High error rate threshold: 62.5% 5xx errors on payment routing paths"),
        (7.6, "web-ui", "critical", "Checkout error rate spike: 54% customer transaction failure rate"),
        (7.7, "api-gateway", "error", "503 Service Unavailable: fallback route active for payment transactions"),
        (7.8, "web-ui", "error", "User transaction error: payment processing unavailable for session #9488"),
        # t_s 8.0 - 8.5: Restart 4 fails, gateway & ui heavily impacted
        (8.0, "api-gateway", "error", "Upstream connection refused: payment-service:8082 host unreachable in service discovery"),
        (8.1, "web-ui", "critical", "Frontend telemetry: user checkout drop-off surge (>65% cart abandonment)"),
        (8.2, "api-gateway", "error", "503 Service Unavailable: payment-service endpoints unhealthy in endpoint slice"),
        (8.4, "api-gateway", "critical", "Gateway degraded: payment routing cluster offline"),
        (8.5, "web-ui", "critical", "Checkout failed: payment transaction pipeline completely unresponsive")
    ]

    # Verify counts
    assert len(raw_alerts) == 31, f"Expected 31 alerts, got {len(raw_alerts)}"
    ps_count = sum(1 for _, svc, _, _ in raw_alerts if svc == "payment-service")
    gw_count = sum(1 for _, svc, _, _ in raw_alerts if svc == "api-gateway")
    ui_count = sum(1 for _, svc, _, _ in raw_alerts if svc == "web-ui")
    assert (ps_count, gw_count, ui_count) == (8, 14, 9), f"Mismatch: {(ps_count, gw_count, ui_count)}"

    alerts = []
    for idx, (t_s, svc, sev, msg) in enumerate(raw_alerts, 1):
        alerts.append({
            "id": f"a-{idx:03d}",
            "t_s": t_s,
            "service": svc,
            "severity": sev,
            "message": msg
        })

    # 4. Logs (~50 lines per service)
    # payment-service: shows startup, then "config error: invalid value for PAYMENT_TIMEOUT_MS: 'abc'"
    # and a stack-trace-style exit, repeated per restart attempt, with the config error at a fixed, citable line number.
    # We place the citable error line at line 24.
    logs = {
        "payment-service": [],
        "api-gateway": [],
        "web-ui": [],
        "auth-service": [],
        "postgres": []
    }

    # payment-service logs (50 lines)
    # Line 1-20: initial boot steps
    # Line 21-30: restart 1 with config error at line 24 and stack trace
    # Line 31-40: restart 2 with config error and stack trace
    # Line 41-50: restart 3 with config error and stack trace
    ps_log_defs = [
        (1, 1.0, "2026-10-09 03:14:00.100 [INFO] Container runtime starting payment-service (image: payment-service:rev-7)"),
        (2, 1.1, "2026-10-09 03:14:00.210 [INFO] Linux kernel 5.15.0-89-generic x86_64; cgroup v2 initialized"),
        (3, 1.2, "2026-10-09 03:14:00.320 [INFO] Loading application environment variables from /etc/config/app.env"),
        (4, 1.5, "2026-10-09 03:14:00.410 [INFO] Environment loaded: PORT=8082, DB_POOL_SIZE=10, RETRY_ATTEMPTS=3"),
        (5, 2.0, "2026-10-09 03:14:00.520 [INFO] Initializing payment provider clients: Stripe v12.4, Adyen v9.1"),
        (6, 2.2, "2026-10-09 03:14:00.650 [INFO] Initializing postgres database connection pool to postgres:5432..."),
        (7, 2.5, "2026-10-09 03:14:00.780 [INFO] Postgres pool connected: 10 connections established, ping 0.8ms"),
        (8, 2.8, "2026-10-09 03:14:00.890 [INFO] Registering payment webhook handlers on /webhooks/stripe, /webhooks/adyen"),
        (9, 3.0, "2026-10-09 03:14:01.010 [INFO] TLS certificates loaded from /etc/tls/certs/payment-tls.crt"),
        (10, 3.2, "2026-10-09 03:14:01.120 [INFO] HTTP server bound to 0.0.0.0:8082, worker concurrency=4"),
        (11, 3.5, "2026-10-09 03:14:01.250 [INFO] Service discovery registered: payment-service.default.svc.cluster.local"),
        (12, 3.8, "2026-10-09 03:14:01.380 [INFO] Health probe handler listening on /healthz and /ready"),
        (13, 4.0, "2026-10-09 03:14:01.500 [INFO] Readiness check passed: all dependencies online"),
        (14, 4.2, "2026-10-09 03:14:01.620 [INFO] Revision 6 successfully serving traffic, request count=1420"),
        (15, 4.4, "2026-10-09 03:14:01.750 [INFO] Rolling update triggered: updating deployment to revision 7"),
        (16, 4.6, "2026-10-09 03:14:01.890 [INFO] Kubelet creating container payment-service for pod payment-service-7f49c8dbb6-q8x2m"),
        (17, 4.7, "2026-10-09 03:14:02.010 [INFO] Pulling configmap payment-config (revision 7)... updated 12s ago"),
        (18, 4.8, "2026-10-09 03:14:02.150 [INFO] Injected environment variable PAYMENT_TIMEOUT_MS='abc'"),
        (19, 4.9, "2026-10-09 03:14:02.260 [INFO] Starting payment-service bootstrap sequence (PID 1)"),
        (20, 4.95, "2026-10-09 03:14:02.350 [INFO] Parsing application timeout settings from environment"),
        (21, 5.0, "2026-10-09 03:14:02.401 [DEBUG] Reading PAYMENT_TIMEOUT_MS from os.environ"),
        (22, 5.0, "2026-10-09 03:14:02.405 [DEBUG] Attempting integer parse for timeout duration in milliseconds"),
        (23, 5.0, "2026-10-09 03:14:02.410 [ERROR] config parsing failed during application bootstrap"),
        # Citable line 24
        (24, 5.0, "2026-10-09 03:14:02.412 [ERROR] config error: invalid value for PAYMENT_TIMEOUT_MS: 'abc'"),
        (25, 5.0, "2026-10-09 03:14:02.415 Traceback (most recent call last):"),
        (26, 5.0, "2026-10-09 03:14:02.418   File \"/app/config.py\", line 42, in load_config"),
        (27, 5.0, "2026-10-09 03:14:02.420     timeout_ms = int(os.environ.get('PAYMENT_TIMEOUT_MS', '3000'))"),
        (28, 5.0, "2026-10-09 03:14:02.423 ValueError: invalid literal for int() with base 10: 'abc'"),
        (29, 5.0, "2026-10-09 03:14:02.425   File \"/app/main.py\", line 18, in <module>"),
        (30, 5.0, "2026-10-09 03:14:02.428 [FATAL] Process exited with status code 1. Terminating container."),
        # Restart attempt 2 (t_s 6.0)
        (31, 5.8, "2026-10-09 03:14:03.100 [INFO] Kubelet restarting container payment-service (attempt 2)..."),
        (32, 5.9, "2026-10-09 03:14:03.220 [INFO] Container payment-service restarted. Bootstrapping PID 1"),
        (33, 6.0, "2026-10-09 03:14:03.350 [INFO] Parsing application timeout settings from environment"),
        (34, 6.1, "2026-10-09 03:14:03.401 [DEBUG] Reading PAYMENT_TIMEOUT_MS from os.environ"),
        (35, 6.2, "2026-10-09 03:14:03.412 [ERROR] config error: invalid value for PAYMENT_TIMEOUT_MS: 'abc'"),
        (36, 6.2, "2026-10-09 03:14:03.415 Traceback (most recent call last):"),
        (37, 6.2, "2026-10-09 03:14:03.418   File \"/app/config.py\", line 42, in load_config"),
        (38, 6.2, "2026-10-09 03:14:03.420     timeout_ms = int(os.environ.get('PAYMENT_TIMEOUT_MS', '3000'))"),
        (39, 6.2, "2026-10-09 03:14:03.423 ValueError: invalid literal for int() with base 10: 'abc'"),
        (40, 6.2, "2026-10-09 03:14:03.428 [FATAL] Process exited with status code 1. Terminating container."),
        # Restart attempt 3 (t_s 7.2)
        (41, 7.0, "2026-10-09 03:14:04.100 [INFO] Kubelet restarting container payment-service (attempt 3)..."),
        (42, 7.1, "2026-10-09 03:14:04.220 [INFO] Container payment-service restarted. Bootstrapping PID 1"),
        (43, 7.2, "2026-10-09 03:14:04.350 [INFO] Parsing application timeout settings from environment"),
        (44, 7.3, "2026-10-09 03:14:04.401 [DEBUG] Reading PAYMENT_TIMEOUT_MS from os.environ"),
        (45, 7.4, "2026-10-09 03:14:04.412 [ERROR] config error: invalid value for PAYMENT_TIMEOUT_MS: 'abc'"),
        (46, 7.4, "2026-10-09 03:14:04.415 Traceback (most recent call last):"),
        (47, 7.4, "2026-10-09 03:14:04.418   File \"/app/config.py\", line 42, in load_config"),
        (48, 7.4, "2026-10-09 03:14:04.420     timeout_ms = int(os.environ.get('PAYMENT_TIMEOUT_MS', '3000'))"),
        (49, 7.4, "2026-10-09 03:14:04.423 ValueError: invalid literal for int() with base 10: 'abc'"),
        (50, 7.4, "2026-10-09 03:14:04.428 [FATAL] Process exited with status code 1. CrashLoopBackOff active.")
    ]
    for line, t_s, text in ps_log_defs:
        logs["payment-service"].append({"line": line, "t_s": t_s, "text": text})

    # api-gateway logs (50 lines)
    # Starts healthy; after t_s 5.0 logs upstream errors and circuit breaker
    for line in range(1, 51):
        t_s = round(0.2 * line, 2)
        if line <= 25:
            text = f"2026-10-09 03:14:0{t_s:.1f} [INFO] [req-{1000+line}] Proxying route /api/v1/auth to auth-service:8081 - 200 OK (12ms)"
        elif line <= 30:
            text = f"2026-10-09 03:14:0{t_s:.1f} [ERROR] [req-{1000+line}] Upstream error connecting to payment-service:8082: connection refused"
        elif line <= 40:
            text = f"2026-10-09 03:14:0{t_s:.1f} [ERROR] [req-{1000+line}] 503 Service Unavailable returned to client for /api/v1/payments/charge"
        else:
            text = f"2026-10-09 03:14:0{t_s:.1f} [WARN] [req-{1000+line}] Circuit breaker OPEN: fast-failing request for payment-service"
        logs["api-gateway"].append({"line": line, "t_s": t_s, "text": text})

    # web-ui logs (50 lines)
    # Starts healthy; after t_s 5.4 logs checkout failures
    for line in range(1, 51):
        t_s = round(0.2 * line, 2)
        if line <= 26:
            text = f"2026-10-09 03:14:0{t_s:.1f} [INFO] [session-usr-{200+line}] Render page /products/{line} status=200 response_time=18ms"
        elif line <= 38:
            text = f"2026-10-09 03:14:0{t_s:.1f} [ERROR] [session-usr-{200+line}] Checkout POST /api/v1/checkout failed: 503 Service Unavailable"
        else:
            text = f"2026-10-09 03:14:0{t_s:.1f} [CRITICAL] [session-usr-{200+line}] Payment transaction failed: downstream gateway unavailable"
        logs["web-ui"].append({"line": line, "t_s": t_s, "text": text})

    # auth-service logs (50 lines) - unaffected, healthy throughout
    for line in range(1, 51):
        t_s = round(0.2 * line, 2)
        text = f"2026-10-09 03:14:0{t_s:.1f} [INFO] [auth-worker-0] JWT token validated for user #{500+line}; redis session cache hit (0.4ms)"
        logs["auth-service"].append({"line": line, "t_s": t_s, "text": text})

    # postgres logs (50 lines) - unaffected, healthy throughout
    for line in range(1, 51):
        t_s = round(0.2 * line, 2)
        text = f"2026-10-09 03:14:0{t_s:.1f} [LOG] Connection pool active: 18/64 connections; checkpoint complete; latency 1.1ms"
        logs["postgres"].append({"line": line, "t_s": t_s, "text": text})

    # 5. Fix definition
    fix = {
        "action": "rollback_deployment",
        "from": "payment-service:rev-7",
        "to": "payment-service:rev-6"
    }

    scenario = {
        "id": "bad_config",
        "title": "Payment Service Bad Config CrashLoop",
        "root_service": "payment-service",
        "duration_s": 12,
        "metrics": metrics,
        "events": events,
        "logs": logs,
        "alerts": alerts,
        "fix": fix
    }

    return scenario


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    output_path = repo_root / "backend" / "scenarios" / "bad_config.json"
    scenario = generate_bad_config()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=2)

    if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print(f"Generated bad_config.json with {len(scenario['alerts'])} alerts.")


if __name__ == "__main__":
    main()
