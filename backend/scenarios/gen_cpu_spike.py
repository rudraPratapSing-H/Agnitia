#!/usr/bin/env python3
"""
gen_cpu_spike.py  --  Generate backend/scenarios/cpu_spike.json
Fixed seed=42, fully deterministic. Run from the repo root or the scenarios dir.

Spec:
  root_service: auth-service
  impacted:     api-gateway, web-ui  (payment-service, postgres, redis stay healthy)
  duration_s:   12
  metrics:      auth-service cpu_pct ramps 20->98 over 0.0-5.0 s (0.5s steps), then pinned
  alerts:       exactly 24, t_s in [5.5, 8.5]  - auth:6  api-gateway:11  web-ui:7
  logs:         ~50 lines per alerting service, citable "CPU throttling detected" on auth-service
  events:       CPUThrottlingHigh
  fix:          patch_cpu_limit  250m->1000m
"""
import json, math, random
from pathlib import Path

random.seed(42)
SCRIPT_DIR = Path(__file__).resolve().parent
OUT = SCRIPT_DIR / "cpu_spike.json"

# ── helpers ──────────────────────────────────────────────────────────────────
def r2(x): return round(x, 2)

# ── metrics ───────────────────────────────────────────────────────────────────
# auth-service: cpu ramps 20->98 over 0.0-5.0 s (11 points), then pinned at 98
# latency: mem_mb stays ~55 (no leak, just CPU)
metrics_auth = []
ramp_steps = 11            # t_s 0.0 … 5.0 in 0.5 s increments
for i in range(ramp_steps):
    t = round(i * 0.5, 1)
    cpu = r2(20.0 + (98.0 - 20.0) * i / (ramp_steps - 1))
    mem = r2(55.0 + random.uniform(-0.3, 0.3))
    metrics_auth.append({"t_s": t, "mem_mb": mem, "cpu_pct": cpu})
# pinned for 5.5..8.5 (7 more points)
for i in range(1, 8):
    t = round(5.0 + i * 0.5, 1)
    cpu = r2(98.0 + random.uniform(-0.2, 0.2))
    mem = r2(55.0 + random.uniform(-0.3, 0.3))
    metrics_auth.append({"t_s": t, "mem_mb": mem, "cpu_pct": cpu})

# ── events ────────────────────────────────────────────────────────────────────
events = [
    {"t_s": 3.0, "service": "auth-service",
     "text": "CPUThrottlingHigh: throttled 87% of period on container auth"},
    {"t_s": 4.5, "service": "auth-service",
     "text": "CPUThrottlingHigh: throttled 96% of period on container auth"},
    {"t_s": 5.5, "service": "auth-service",
     "text": "CPUThrottlingHigh: throttled 99% of period on container auth"},
]

# ── logs  ~50 lines per service ───────────────────────────────────────────────
auth_log_texts = [
    (0.2, "auth-service starting up on port 8080"),
    (0.5, "JWT validation worker pool initialized: 4 threads"),
    (0.8, "bcrypt cost factor: 12 (estimated 180 ms/op)"),
    (1.0, "CPU throttling detected: current utilization 38%"),           # citable line
    (1.2, "worker pool queue depth: 12 tasks"),
    (1.5, "bcrypt throughput: 5.4 ops/s (expected 16)"),
    (1.8, "HTTP/2 handler: 48 concurrent streams"),
    (2.0, "CPU utilization crossing 50% — throttling imminent"),
    (2.2, "bcrypt worker queue depth: 28"),
    (2.5, "p50 latency: 980 ms  p99 latency: 2100 ms"),
    (2.8, "connection pool: 120/128 slots occupied"),
    (3.0, "WARN: CPU throttling active — throttle ratio 87%"),
    (3.2, "bcrypt worker pool saturated: 64 tasks queued"),
    (3.5, "p99 request latency: 3400 ms (threshold 2000 ms)"),
    (3.8, "k8s liveness probe response: 201ms (limit 200ms) — degraded"),
    (4.0, "WARN: CPU throttle ratio 94% — request queue growing"),
    (4.2, "worker pool rejection rate: 12 req/s"),
    (4.5, "upstream timeout returned to api-gateway after 5000ms"),
    (4.8, "p99 latency: 5800 ms — SLO breach"),
    (5.0, "CPU throttle ratio: 99% — effective parallelism: 1 thread"),
    (5.2, "bcrypt queue depth: 128, dropping oldest tasks"),
    (5.5, "ERROR: 503 returned for /api/v1/token (upstream saturation)"),
    (5.8, "liveness probe missed — kubelet may mark pod unhealthy"),
    (6.0, "CRITICAL: CPU saturation — all compute allocated to bcrypt"),
    (6.2, "request timeout: POST /api/v1/session 5000ms exceeded"),
    (6.5, "ERROR: connection refused to redis — worker threads exhausted"),
    (6.8, "queue overflow: 256 tasks dropped in last 500ms window"),
    (7.0, "auth-service token issuance rate: 0 tokens/s"),
    (7.2, "health endpoint /healthz returning 503"),
    (7.5, "ERROR: upstream auth-service unreachable from api-gateway"),
    (7.8, "CPU throttle ratio: 99.4% — system effectively stalled"),
    (8.0, "CRITICAL: SLO breach — p99 latency 8200ms vs 2000ms SLO"),
    (8.2, "bcrypt cost factor may be too high for current CPU limit"),
    (8.5, "readiness probe failed: GET /readyz 503 after 1200ms"),
    (8.8, "Kubernetes eviction candidate — pod priority: 0"),
    (9.0, "Diagnostic: CPU request 250m, limit 250m, actual usage 1000m"),
    (9.3, "Suggest: increase cpu limit to at least 1000m (4x current)"),
    (9.5, "Worker pool: 0 available threads, 512 queued tasks"),
    (9.8, "token issuance failure rate: 100%"),
    (10.0, "Auth service fully degraded — no tokens being issued"),
    (10.3, "ERROR: multiple downstream dependencies reporting auth failures"),
    (10.5, "bcrypt computation estimate at current CPU: 3600 ms/hash"),
    (10.8, "p99: 9800ms — 100% of traffic exceeding SLO threshold"),
    (11.0, "CRITICAL: Service effectively unresponsive since t_s=5.0"),
    (11.2, "CPU throttle event count: 420 in last 60s window"),
    (11.5, "Operator alert: patch_cpu_limit recommended — from 250m to 1000m"),
    (11.8, "Ready for remediation: kubectl patch deployment auth-service"),
]
auth_logs = [{"line": i+1, "t_s": t, "text": txt} for i,(t,txt) in enumerate(auth_log_texts)]

api_gw_log_texts = [
    (5.5, "Upstream auth-service circuit-breaker OPEN (failure rate 100%)"),
    (5.6, "504 Gateway Timeout: /api/v1/checkout → auth-service"),
    (5.7, "Retry budget exhausted: auth-service (3/3 retries timed out)"),
    (5.8, "Error rate: 78% over last 30s window"),
    (5.9, "WARN: Connection pool to auth-service drained"),
    (6.0, "Alertmanager: P1 alert fired — api-gateway 504 rate > 50%"),
    (6.1, "504 Gateway Timeout: /api/v1/login → auth-service"),
    (6.2, "p99 latency to client: 5900ms"),
    (6.3, "Circuit breaker half-open probe: auth-service returned 503"),
    (6.4, "auth-service endpoint marked UNHEALTHY in service mesh"),
    (6.5, "504 Gateway Timeout: /api/v1/payment-init → auth-service"),
    (6.6, "Error rate: 94% — degraded mode active"),
    (6.7, "Serving 503 for all auth-dependent routes"),
    (6.8, "Throughput: 0 successful requests/s"),
    (7.0, "Health endpoint /healthz returns degraded"),
    (7.2, "Request queue: 512 pending, 0 being served"),
    (7.5, "504 Gateway Timeout: /api/v1/logout → auth-service"),
    (7.8, "Kubernetes readiness probe: FAIL"),
    (8.0, "SLO breach: error budget consumed — rolling back traffic"),
    (8.2, "Standby instance warming up for failover"),
    (8.5, "Connection refused on upstream port 8080 after 500ms"),
    (9.0, "auth-service unreachable: all 5 replicas returning 503"),
    (9.5, "Serving fallback 503 for all endpoints"),
    (10.0, "CRITICAL: API Gateway fully degraded"),
    (10.5, "Alertmanager: API gateway error rate 100% for >5 minutes"),
    (11.0, "Retrying auth-service probe..."),
    (11.5, "Probe response: 503 Service Unavailable"),
    (12.0, "Still degraded — awaiting remediation"),
]
api_gw_logs = [{"line": i+1, "t_s": t, "text": txt} for i,(t,txt) in enumerate(api_gw_log_texts)]

web_ui_log_texts = [
    (5.7, "Checkout flow: auth token request timed out after 5000ms"),
    (5.8, "User-facing error: 'Login failed — please try again'"),
    (5.9, "Session establishment failed: upstream 504"),
    (6.0, "Login success rate: 0%"),
    (6.2, "Session pool stale: 1024 expired sessions not renewed"),
    (6.5, "WebSocket connection drop: auth token refresh failed"),
    (6.8, "Cart checkout failure: 503 from api-gateway"),
    (7.0, "CRITICAL: All authenticated features unavailable"),
    (7.2, "Serving static content only — dynamic routes failing"),
    (7.5, "Error page shown to 100% of users attempting login"),
    (7.8, "Payment flow: authentication step failed — transaction aborted"),
    (8.0, "User session timeout cascade: 8420 sessions dropped"),
    (8.2, "Fallback mode active: showing maintenance banner"),
    (8.5, "HTTP 503 served for /dashboard, /checkout, /account"),
    (9.0, "Retry: auth endpoint 5 consecutive 504 responses"),
    (9.5, "Graceful degradation: read-only product catalog available"),
    (10.0, "Revenue impact: 100% of checkout flow blocked"),
    (10.5, "CRITICAL: All transactional features unavailable"),
    (11.0, "Alert: web-ui degraded SLO for >5 minutes"),
    (11.5, "Waiting for auth-service recovery to restore sessions"),
]
web_ui_logs = [{"line": i+1, "t_s": t, "text": txt} for i,(t,txt) in enumerate(web_ui_log_texts)]

# ── alerts: 24 total, t_s in [5.5, 8.5]  auth:6  api-gateway:11  web-ui:7 ──
def spread_times(n, lo, hi):
    step = (hi - lo) / (n - 1)
    return [round(lo + i * step, 2) for i in range(n)]

auth_times    = spread_times(6,  5.5, 7.5)
gw_times      = spread_times(11, 5.5, 8.5)
ui_times      = spread_times(7,  5.6, 8.3)

auth_msgs = [
    "CPUThrottlingHigh: auth-service throttled 99% of period",
    "p99 request latency 6200ms exceeds SLO threshold 2000ms",
    "Token issuance rate 0 tokens/s — complete CPU starvation",
    "Readiness probe failed: GET /readyz returned 503",
    "Worker thread pool exhausted: 512 queued, 0 active",
    "CRITICAL: CPU limit 250m insufficient — sustained 100% throttle",
]
gw_msgs = [
    "504 Gateway Timeout from upstream auth-service (attempt 1/3)",
    "Circuit breaker OPEN: auth-service failure rate 100%",
    "P99 latency 5900ms exceeds SLO — api-gateway degraded",
    "Upstream auth-service connection pool drained",
    "504 Gateway Timeout: /api/v1/checkout → auth-service (attempt 2/3)",
    "Error rate 78% over 30s window — SLO breach",
    "504 Gateway Timeout: /api/v1/login (retry budget exhausted)",
    "All auth-dependent routes returning 503",
    "api-gateway readiness probe: FAIL — serving degraded traffic",
    "Throughput: 0 successful requests/s for >3 minutes",
    "CRITICAL: API Gateway error rate 100% — full impact",
]
ui_msgs = [
    "Login flow: auth token request timed out (5000ms)",
    "Checkout error: 503 Service Unavailable from api-gateway",
    "Session renewal failure: upstream auth-service 504",
    "User-facing 504 error rate: 100%",
    "Cart checkout blocked: authentication step failed",
    "Payment flow aborted: could not obtain auth token",
    "CRITICAL: All transactional features unavailable for >5 minutes",
]

alerts = []
ctr = 1
for t, msg in zip(auth_times, auth_msgs):
    alerts.append({"id": f"a-cs{ctr:03d}", "t_s": t, "service": "auth-service",
                   "severity": "critical", "message": msg})
    ctr += 1
for t, msg in zip(gw_times, gw_msgs):
    alerts.append({"id": f"a-cs{ctr:03d}", "t_s": t, "service": "api-gateway",
                   "severity": "critical" if "CRITICAL" in msg or "504" in msg else "warning", "message": msg})
    ctr += 1
for t, msg in zip(ui_times, ui_msgs):
    alerts.append({"id": f"a-cs{ctr:03d}", "t_s": t, "service": "web-ui",
                   "severity": "critical" if "CRITICAL" in msg else "warning", "message": msg})
    ctr += 1
alerts.sort(key=lambda a: a["t_s"])

assert len(alerts) == 24, f"Expected 24 alerts, got {len(alerts)}"
from collections import Counter
c = Counter(a["service"] for a in alerts)
assert c["auth-service"] == 6 and c["api-gateway"] == 11 and c["web-ui"] == 7

# ── assemble ──────────────────────────────────────────────────────────────────
scenario = {
    "id": "cpu_spike",
    "title": "Auth Service CPU Saturation Spike",
    "root_service": "auth-service",
    "duration_s": 12,
    "metrics": {
        "auth-service": metrics_auth,
    },
    "events": events,
    "logs": {
        "auth-service": auth_logs,
        "api-gateway":  api_gw_logs,
        "web-ui":       web_ui_logs,
    },
    "alerts": alerts,
    "fix": {
        "action": "patch_cpu_limit",
        "from": "250m",
        "to": "1000m",
    },
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(scenario, f, indent=2)
print(f"Written {OUT}")
print(f"Alerts: {len(alerts)} total — auth:{c['auth-service']} api-gateway:{c['api-gateway']} web-ui:{c['web-ui']}")
