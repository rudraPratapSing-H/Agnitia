# Agnitia — Data Contract

> **Contract Freeze:** Locked in Hour 0. All layers (Frontend, Backend, AI Agents, Integrations) build against this contract. Changes require consensus across all lanes.

---

## 1. Service Topology & Dependency Graph

Agnitia monitors a 6-service microservices topology arranged in 4 tiers:

```
[ Tier: frontend ]          web-ui
                              │
[ Tier: edge ]           api-gateway
                              │
                    ┌─────────┴─────────┐
[ Tier: backend ] auth-service    payment-service
                    │         │         │
                    │         └────┬────┘
                    ▼              ▼
[ Tier: data ]    redis         postgres
```

### Dependency Definitions
- `web-ui` depends on `api-gateway`
- `api-gateway` depends on `auth-service` and `payment-service`
- `auth-service` depends on `postgres` and `redis`
- `payment-service` depends on `postgres`
- `postgres` has NO dependencies
- `redis` has NO dependencies

### Correlation & Root-Cause Rule
1. An alerting service is the **root cause** if none of its dependencies are currently alerting.
2. Every alerting service downstream of the root joins the root's incident.
3. For the **Database Out-of-Memory (`db_oom`)** fault:
   - `postgres`: 1 alert (root cause)
   - `auth-service`: 10 alerts (impacted)
   - `payment-service`: 15 alerts (impacted)
   - `api-gateway`: 18 alerts (impacted)
   - `web-ui`: 12 alerts (impacted)
   - **Total alerts = 56** collapsed into 1 incident.
   - `redis` remains **healthy** (proves graph-aware alert correlation, not naive time-window clustering).

---

## 2. Core Data Models

### 2.1 ServiceNode
```json
{
  "id": "postgres",
  "label": "PostgreSQL",
  "tier": "data",
  "depends_on": [],
  "status": "healthy",
  "metrics": {
    "mem_mb": 58,
    "mem_limit_mb": 64,
    "cpu_pct": 12,
    "restarts": 0
  }
}
```
- **`tier`**: `"data"` | `"backend"` | `"edge"` | `"frontend"`
- **`status`**: `"healthy"` | `"root_cause"` | `"impacted"` | `"recovering"`

### 2.2 Alert
```json
{
  "id": "a-017",
  "ts": "2026-10-09T03:14:09Z",
  "service": "api-gateway",
  "severity": "critical",
  "message": "502 Bad Gateway: upstream auth-service unavailable",
  "incident_id": "INC-104"
}
```
- **`severity`**: `"info"` | `"warning"` | `"error"` | `"critical"`

### 2.3 EvidenceItem
```json
{
  "type": "k8s_event",
  "source": "postgres-0",
  "line": null,
  "text": "Reason: OOMKilled, Exit Code: 137",
  "verified": true
}
```
- **`type`**: `"k8s_event"` | `"log"` | `"metric"`

### 2.4 PlaybookStep
```json
{
  "order": 1,
  "service": "postgres",
  "action": "patch_memory_limit",
  "params": {
    "from": "64Mi",
    "to": "256Mi"
  },
  "risk": "high",
  "requires_approval": true,
  "verify": "port 5432 accepting connections"
}
```
- **`risk`**: `"low"` | `"medium"` | `"high"`

### 2.5 Safety Allow-List for Actions
Only safe recovery actions may be proposed by the planner agent or executed by the executor:
1. `patch_memory_limit`
2. `patch_cpu_limit`
3. `rollout_restart`
4. `rollback_deployment`
5. `scale_replicas`
6. `wait_for_ready`
7. `verify_health`

> **Safety Guarantee:** Deletion actions (`delete_pod`, `drop_database`, `delete_namespace`) are strictly prohibited and rejected by the execution engine.

### 2.6 Incident
```json
{
  "id": "INC-104",
  "status": "awaiting_approval",
  "scenario": "db_oom",
  "root_service": "postgres",
  "impacted_services": ["auth-service", "payment-service", "api-gateway", "web-ui"],
  "raw_alert_count": 56,
  "started_at": "2026-10-09T03:14:07Z",
  "resolved_at": null,
  "rca": {
    "root_cause": "PostgreSQL was killed for exceeding its 64Mi memory limit",
    "category": "OOMKilled",
    "confidence": 0.97,
    "evidence": [
      { "type": "k8s_event", "source": "postgres-0", "text": "Reason: OOMKilled, Exit Code: 137", "verified": true },
      { "type": "log", "source": "postgres-0", "line": 42, "text": "FATAL: out of memory", "verified": true },
      { "type": "metric", "source": "postgres-0", "text": "memory 63.8Mi of 64Mi limit at 03:14:05", "verified": true }
    ],
    "similar_incident": { "id": "INC-087", "similarity": 0.94 }
  },
  "playbook": {
    "diff": "resources.limits.memory: 64Mi -> 256Mi",
    "steps": [
      { "order": 1, "service": "postgres", "action": "patch_memory_limit", "params": { "from": "64Mi", "to": "256Mi" }, "risk": "high", "requires_approval": true, "verify": "port 5432 accepting connections" },
      { "order": 2, "service": "postgres", "action": "wait_for_ready", "params": { "timeout_s": 30 }, "risk": "low", "requires_approval": false, "verify": "readiness probe passes" },
      { "order": 3, "service": "auth-service", "action": "rollout_restart", "risk": "low", "requires_approval": false, "verify": "health endpoint 200" },
      { "order": 4, "service": "payment-service", "action": "rollout_restart", "risk": "low", "requires_approval": false, "verify": "health endpoint 200" },
      { "order": 5, "service": "api-gateway", "action": "verify_health", "risk": "low", "requires_approval": false, "verify": "error rate below 1%" }
    ]
  },
  "timeline": [
    { "t_s": 0, "event": "First alert received" }
  ]
}
```
- **`status`**: `"detected"` | `"analyzing"` | `"awaiting_approval"` | `"healing"` | `"resolved"`

---

## 3. WebSocket Event Envelope

All real-time events sent over `/ws` share a common envelope:

```json
{
  "type": "agent_step",
  "ts": "2026-10-09T03:14:11Z",
  "payload": {
    "agent": "diagnose",
    "text": "Reading last 50 log lines from postgres-0",
    "status": "running"
  }
}
```

### Event Types:
| `type` | Payload Description |
|---|---|
| `alert` | Single `Alert` object emitted during fault injection |
| `service_update` | Updated `ServiceNode` state (e.g. status transition, metrics) |
| `incident_update` | Current `Incident` object (updates status, RCA, playbook) |
| `agent_step` | Agent investigation progress: `{"agent": str, "text": str, "status": "pending"\|"running"\|"done"\|"failed"}` |
| `playbook_step` | Execution step progress: `{"order": int, "service": str, "status": str, "action": str}` |
| `metric_point` | Single metric tick: `{"service": str, "t_s": float, "mem_mb": float, "cpu_pct": float}` |
| `prediction` | Early crash warning: `{"service": str, "seconds": float, "message": str}` |
| `reset` | Emitted when system is reset to all-green state: `{}` |

---

## 4. REST Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chaos/{scenario}` | Inject fault scenario (`db_oom`, `bad_config`, `cpu_spike`, `slow_leak`) |
| `POST` | `/api/reset` | Restore entire topology to healthy state and reset metrics |
| `POST` | `/api/incidents/{id}/approve` | Authorize playbook execution (called by UI & Telegram Bot) |
| `POST` | `/api/incidents/{id}/reject` | Reject/cancel playbook execution |
| `GET` | `/api/incidents/latest` | Retrieve current/latest incident (polled by bot & frontend) |
| `GET` | `/api/incidents/{id}/postmortem` | Return generated postmortem in Markdown format |
| `GET` | `/api/blast-radius/{service}` | Return downstream services and estimated impact |
| `POST` | `/api/autonomy` | Set autonomy policy level (1, 2, or 3) |
| `WS` | `/ws` | Live WebSocket event stream |
