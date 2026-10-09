#!/usr/bin/env python3
"""
gen_slow_leak.py  --  Generate backend/scenarios/slow_leak.json
Fixed seed=42, fully deterministic. Run from the repo root or the scenarios dir.

Spec:
  root_service: postgres
  impacted:     auth-service, payment-service, api-gateway, web-ui (same as db_oom)
  duration_s:   250
  preventive_fix_at_s: 180   (hint for predictor demo)

  metrics:  postgres mem_mb ramps 40.0 -> ~63.9 over 0.0 - 240.0 s (0.5 s steps, 481 points)
            with small deterministic noise; trend positive in every window of 20 consecutive points.
  events:   gradual warnings, OOMKilled at t_s 240.0
  logs:     ~50 lines per postgres with memory-pressure progression,
            citable "FATAL: out of memory" line
  alerts:   NO alerts before 240.0. After crash same 56-alert storm as db_oom,
            starting at t_s 240.2: postgres:1 auth:10 payment:15 api-gateway:18 web-ui:12
  fix:      patch_memory_limit  64Mi -> 256Mi
"""
import json, math, random
from pathlib import Path
from collections import Counter

random.seed(42)
SCRIPT_DIR = Path(__file__).resolve().parent
OUT = SCRIPT_DIR / "slow_leak.json"

# ── memory ramp ───────────────────────────────────────────────────────────────
# Linear from 40.0 to 63.9 over 240 s, 0.5 s steps -> 481 points (t_s 0.0..240.0)
START_MEM  = 40.0
END_MEM    = 63.9
CRASH_T    = 240.0
STEP       = 0.5
N_POINTS   = int(CRASH_T / STEP) + 1   # 481

# Noise: tiny per-step additive, reset each window to keep trend always positive.
# Strategy: add small noise but guarantee each point >= previous (monotone).
# Then add a tiny jitter that can go slightly negative — but stay positive in
# any 20-point window by construction.
slope = (END_MEM - START_MEM) / CRASH_T   # MB per second

# We want noise such that in any 20-point window (10 s span) the net change is positive.
# 10 s span * slope = 0.99 MB minimum gain. Noise amplitude < 0.99/20 = 0.0495 MB.
NOISE_AMP = 0.04   # safe

metrics_postgres = []
prev_mem = START_MEM
for i in range(N_POINTS):
    t = round(i * STEP, 1)
    ideal = START_MEM + slope * t
    # Add small bounded random perturbation, biased slightly positive
    noise = random.uniform(-NOISE_AMP, NOISE_AMP * 1.2)
    mem = round(ideal + noise, 2)
    # Clamp: never below 40.0, never above 63.95
    mem = max(START_MEM, min(63.95, mem))
    cpu = round(12.0 + 0.005 * t + random.uniform(-0.3, 0.3), 2)
    metrics_postgres.append({"t_s": t, "mem_mb": mem, "cpu_pct": cpu})
    prev_mem = mem

# Verify: every window of 20 consecutive points has a positive trend
# (slope of linear regression across those points > 0)
pts = [p["mem_mb"] for p in metrics_postgres]
N = len(pts)
for start in range(N - 20):
    window = pts[start:start+20]
    xs = list(range(20))
    xm = sum(xs) / 20
    ym = sum(window) / 20
    num = sum((xs[i]-xm)*(window[i]-ym) for i in range(20))
    den = sum((xs[i]-xm)**2 for i in range(20))
    slope_w = num / den if den else 0
    assert slope_w > 0, f"Non-positive trend in window starting at {start}: slope={slope_w}"

# ── events ────────────────────────────────────────────────────────────────────
events = [
    {"t_s": 30.0,  "service": "postgres", "text": "WARNING: autovacuum worker running longer than expected (45s)"},
    {"t_s": 60.0,  "service": "postgres", "text": "WARNING: shared_buffers usage at 62% — memory pressure rising"},
    {"t_s": 90.0,  "service": "postgres", "text": "WARNING: memory usage 71% — WAL writer buffer approaching limit"},
    {"t_s": 120.0, "service": "postgres", "text": "WARNING: memory usage 78% — consider increasing memory limit"},
    {"t_s": 150.0, "service": "postgres", "text": "WARNING: memory usage 82% — autovacuum paused due to memory pressure"},
    {"t_s": 180.0, "service": "postgres", "text": "CRITICAL: memory usage 88% — approaching container limit 64Mi"},
    {"t_s": 210.0, "service": "postgres", "text": "CRITICAL: memory usage 95% — OOM imminent"},
    {"t_s": 240.0, "service": "postgres", "text": "Reason: OOMKilled, Exit Code: 137 — container exceeded memory limit 64Mi"},
]

# ── logs: ~50 lines for postgres ─────────────────────────────────────────────
pg_log_texts = [
    (0.5,  "PostgreSQL 15.2 on x86_64-pc-linux-gnu started"),
    (1.0,  "listening on IPv4 address 0.0.0.0, port 5432"),
    (2.0,  "shared_buffers = 16MB (container limit 64Mi)"),
    (5.0,  "autovacuum launcher started"),
    (10.0, "checkpoint starting: time"),
    (15.0, "Active connections: 28"),
    (20.0, "autovacuum: VACUUM public.orders (pages 412)"),
    (25.0, "memory usage 45% — buffer cache growing"),
    (30.0, "autovacuum worker running for 45s on table public.sessions"),
    (40.0, "checkpoint complete: wrote 820 buffers (5.0%)"),
    (45.0, "Active connections: 42 — pool pressure increasing"),
    (50.0, "shared_buffers hit ratio: 94.2%"),
    (60.0, "WARN: memory usage 62% — shared buffer cache at capacity"),
    (65.0, "autovacuum: VACUUM public.events (pages 2104)"),
    (70.0, "memory usage 65% — WAL buffer pressure"),
    (75.0, "Active connections: 64"),
    (80.0, "checkpoint starting: wal"),
    (85.0, "slow query: SELECT * FROM sessions WHERE ... 4200ms"),
    (90.0, "WARN: memory usage 71% — WAL writer buffer approaching limit"),
    (100.0, "autovacuum pausing — insufficient memory for sort"),
    (105.0, "memory usage 74% — freeing statement memory"),
    (110.0, "Active connections: 78 — memory per connection: 0.3MB"),
    (120.0, "WARN: memory usage 78% — consider increasing container limit"),
    (125.0, "autovacuum: VACUUM public.audit_log (pages 8840)"),
    (130.0, "work_mem reduced from 4MB to 1MB due to pressure"),
    (135.0, "memory usage 80% — aggressive cache eviction started"),
    (140.0, "checkpoint: 2140 buffers written — I/O spike"),
    (145.0, "Active connections: 88"),
    (150.0, "WARN: memory usage 82% — autovacuum paused"),
    (155.0, "memory usage 83.5% — background worker memory rationing"),
    (160.0, "slow query: UPDATE orders SET ... 8100ms (memory wait)"),
    (165.0, "shared_buffers hit ratio dropped to 78% (eviction storm)"),
    (170.0, "memory usage 85% — pg_freespace map rebuild deferred"),
    (175.0, "Active connections: 96 — rejecting new connections"),
    (180.0, "CRITICAL: memory usage 88% — approaching 64Mi container limit"),
    (185.0, "autovacuum: cannot start — insufficient memory"),
    (190.0, "memory usage 90% — emergency reclaim initiated"),
    (195.0, "OOM risk: rss=57.6MB vs limit=64MB"),
    (200.0, "CRITICAL: memory usage 92% — preparing for graceful shutdown"),
    (205.0, "Active connections: 104"),
    (210.0, "CRITICAL: memory usage 95% — OOM kill imminent"),
    (215.0, "cache thrash: 99% of fetches require disk read"),
    (220.0, "memory usage 97% — rss=62.1MB limit=64MB"),
    (225.0, "ERROR: out of memory for query result"),
    (230.0, "memory usage 99% — rss=63.4MB limit=64MB"),
    (232.0, "Attempting emergency vacuum to reclaim memory..."),
    (235.0, "ERROR: out of memory: failed request size 2097152 bytes"),
    (238.0, "memory usage 99.8% — final metric before OOM"),
    (240.0, "FATAL: out of memory"),                                   # citable line 49
    (240.0, "server process (PID 1) was terminated by signal 9: Killed"),
    (240.0, "terminating all active connections due to server restart"),
]
pg_logs = [{"line": i+1, "t_s": t, "text": txt} for i,(t,txt) in enumerate(pg_log_texts)]

# ── alerts: 56, all t_s >= 240.2, same storm as db_oom ───────────────────────
# Distribution: postgres:1, auth-service:10, payment:15, api-gateway:18, web-ui:12
def jitter_times(base, n, step=0.05):
    ts = []
    t = base
    for i in range(n):
        ts.append(round(t, 2))
        t += step + random.uniform(0, step * 0.3)
    return ts

PG_ALERT_T       = 240.2
AUTH_ALERT_T     = 240.25
PAYMENT_ALERT_T  = 240.3
GW_ALERT_T       = 240.35
UI_ALERT_T       = 240.4

pg_alerts = [
    {"id": "a-sl001", "t_s": PG_ALERT_T, "service": "postgres",
     "severity": "critical",
     "message": "OOMKilled: postgres container exceeded memory limit 64Mi — Exit Code 137"},
]

auth_msgs = [
    "connection refused: postgres:5432 — database restarting",
    "psql: FATAL: the database system is starting up (attempt 1/5)",
    "connection pool timeout: all 20 slots exhausted",
    "ERROR: database connection lost — retrying in 2s",
    "health check failed: postgres unreachable at 5432",
    "psql: FATAL: the database system is starting up (attempt 3/5)",
    "ERROR: cannot connect to database after 10s",
    "session persistence failure: postgres unavailable",
    "auth token validation impossible: DB unreachable",
    "CRITICAL: auth-service fully degraded — postgres offline",
]
auth_alert_ts = jitter_times(AUTH_ALERT_T, 10, 0.08)

payment_msgs = [
    "payment database unavailable: postgres offline (attempt 1/3)",
    "transaction rollback: could not connect to postgres",
    "FATAL: payment processor cannot start without database",
    "connection pool empty: postgres:5432 refusing connections",
    "payment-service: postgres unavailable — all transactions blocked",
    "ERROR: idempotency key store unreachable (postgres down)",
    "psql: FATAL: connection refused to 10.0.0.5:5432",
    "payment retry queue: 1204 pending — database offline",
    "stripe webhook processing halted: cannot write to postgres",
    "CRITICAL: payment-service fully degraded",
    "ERROR: cannot rollback transaction — DB unreachable",
    "reconciliation job failed: postgres connection refused",
    "payment ledger write failed: ERROR connection lost",
    "CRITICAL: 100% transaction failure rate — postgres OOMKilled",
    "audit log write failed: database offline",
]
payment_alert_ts = jitter_times(PAYMENT_ALERT_T, 15, 0.06)

gw_msgs = [
    "circuit breaker OPEN: postgres unreachable (via auth-service)",
    "504 Gateway Timeout: /api/v1/login → auth-service (db offline)",
    "upstream auth-service returning 503 — database offline",
    "circuit breaker OPEN: payment-service unavailable",
    "504 Gateway Timeout: /api/v1/checkout → payment-service",
    "p99 latency: 6100ms — cascading database failure",
    "all backend services degraded — postgres OOMKilled",
    "504 Gateway Timeout: /api/v1/token — auth DB offline",
    "error rate 100%: both auth and payment backends unavailable",
    "circuit breaker HALF-OPEN: probing auth-service…",
    "retry failed: auth-service returned 503 (DB not ready)",
    "504 Gateway Timeout: /api/v1/cart → payment-service",
    "health endpoint /healthz: DEGRADED (2/4 upstreams down)",
    "request queue: 2048 pending, 0 being served",
    "CRITICAL: api-gateway fully degraded — all upstreams failed",
    "client error rate 100% — serving 503 for all endpoints",
    "throughput: 0 successful requests/s for >30s",
    "CRITICAL: SLO breach — all user traffic blocked",
]
gw_alert_ts = jitter_times(GW_ALERT_T, 18, 0.05)

ui_msgs = [
    "login failed: database offline — 'Service temporarily unavailable'",
    "session persistence error: cannot write to auth backend",
    "checkout page: payment service unreachable (503)",
    "cart save failed: backend database offline",
    "user-facing error: 'Something went wrong — please try again'",
    "session expiry cascade: 4200 active sessions dropped",
    "CRITICAL: all transactional features unavailable",
    "health monitor: 0/4 backend services healthy",
    "showing maintenance banner to all users",
    "revenue impact: 100% of orders blocked (postgres OOMKilled)",
    "WebSocket disconnect: auth token renewal impossible",
    "CRITICAL: web-ui fully degraded for >60 seconds",
]
ui_alert_ts = jitter_times(UI_ALERT_T, 12, 0.06)

alerts_slow = pg_alerts.copy()
for t, msg in zip(auth_alert_ts, auth_msgs):
    alerts_slow.append({"id": f"a-sl{len(alerts_slow)+1:03d}", "t_s": t,
                        "service": "auth-service", "severity": "critical", "message": msg})
for t, msg in zip(payment_alert_ts, payment_msgs):
    alerts_slow.append({"id": f"a-sl{len(alerts_slow)+1:03d}", "t_s": t,
                        "service": "payment-service", "severity": "critical", "message": msg})
for t, msg in zip(gw_alert_ts, gw_msgs):
    alerts_slow.append({"id": f"a-sl{len(alerts_slow)+1:03d}", "t_s": t,
                        "service": "api-gateway", "severity": "critical", "message": msg})
for t, msg in zip(ui_alert_ts, ui_msgs):
    alerts_slow.append({"id": f"a-sl{len(alerts_slow)+1:03d}", "t_s": t,
                        "service": "web-ui", "severity": "critical", "message": msg})

alerts_slow.sort(key=lambda a: a["t_s"])

c = Counter(a["service"] for a in alerts_slow)
assert len(alerts_slow) == 56, f"Expected 56 alerts, got {len(alerts_slow)}"
assert c["postgres"] == 1
assert c["auth-service"] == 10
assert c["payment-service"] == 15
assert c["api-gateway"] == 18
assert c["web-ui"] == 12
# All pre-crash alerts must be >= 240.2
for a in alerts_slow:
    assert a["t_s"] >= 240.2, f"Alert before crash: {a}"

# ── assemble ──────────────────────────────────────────────────────────────────
scenario = {
    "id": "slow_leak",
    "title": "PostgreSQL Gradual Memory Leak (OOM after 240s)",
    "root_service": "postgres",
    "duration_s": 250,
    "preventive_fix_at_s": 180,
    "metrics": {
        "postgres": metrics_postgres,
    },
    "events": events,
    "logs": {
        "postgres": pg_logs,
    },
    "alerts": alerts_slow,
    "fix": {
        "action": "patch_memory_limit",
        "from": "64Mi",
        "to": "256Mi",
    },
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(scenario, f, indent=2)

out_str = str(OUT.name)
print(f"Written {out_str}")
print(f"Metric points: {len(metrics_postgres)}")
print(f"Log lines (postgres): {len(pg_logs)}")
print(f"Events: {len(events)}")
print(f"Alerts: {len(alerts_slow)} total - pg:{c['postgres']} auth:{c['auth-service']} payment:{c['payment-service']} gw:{c['api-gateway']} ui:{c['web-ui']}")
print(f"Trend check: PASS (all 20-point windows positive)")
print(f"preventive_fix_at_s: {scenario['preventive_fix_at_s']}")
