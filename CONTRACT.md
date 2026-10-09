## 7. The data contract (lock this in hour 0)

Save this as `CONTRACT.md` in the repo root before anyone writes code. Frontend, backend and AI all build against it, so integration at hours 5 and 11 takes minutes instead of hours.

**The 6 services and the 56 alerts**

- `web-ui` → `api-gateway` → `auth-service` and `payment-service`; `auth-service` → `postgres` and `redis`; `payment-service` → `postgres`
- Database out-of-memory scenario: postgres 1 alert, auth-service 10, payment-service 15, api-gateway 18, web-ui 12 = **56**. Redis stays healthy, which proves the correlation is graph-aware.
- **Correlation rule:** an alerting service is the root if none of its dependencies are alerting. Every alerting service downstream of the root joins the root's incident.

**Service node**

```jsonc
{
  "id": "postgres",
  "label": "PostgreSQL",
  "tier": "data",                 // data | backend | edge | frontend
  "depends_on": [],
  "status": "healthy",            // healthy | root_cause | impacted | recovering
  "metrics": { "mem_mb": 58, "mem_limit_mb": 64, "cpu_pct": 12, "restarts": 0 }
}
```

**Alert**

```jsonc
{
  "id": "a-017",
  "ts": "2026-10-09T03:14:09Z",
  "service": "api-gateway",
  "severity": "critical",
  "message": "502 Bad Gateway: upstream auth-service unavailable",
  "incident_id": "INC-104"
}
```

**Incident, with root cause and playbook**

```jsonc
{
  "id": "INC-104",
  "status": "awaiting_approval",  // detected | analyzing | awaiting_approval | healing | resolved
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
    "similar_incident": { "id": "INC-087", "similarity": 0.94 },   // Feature 17, optional
    "warning": null   // (added, M3): string | null
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
  "timeline": [ { "t_s": 0, "event": "First alert received" } ]
}
```

**Allowed actions (the safety allow-list):** `patch_memory_limit`, `patch_cpu_limit`, `rollout_restart`, `rollback_deployment`, `scale_replicas`, `wait_for_ready`, `verify_health`. Nothing that deletes. Mention this list when judges ask about safety.

**WebSocket event envelope** — every message from backend to frontend:

```jsonc
{ "type": "agent_step", "ts": "2026-10-09T03:14:11Z", "payload": { "agent": "diagnose", "text": "Reading last 50 log lines from postgres-0", "status": "running" } }
// type: alert | service_update | incident_update | agent_step | playbook_step | metric_point | prediction | reset
```

**REST endpoints**

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/chaos/{scenario}` | Inject `db_oom`, `bad_config`, `cpu_spike` or `slow_leak` |
| POST | `/api/reset` | Everything back to green |
| POST | `/api/incidents/{id}/approve` | Authorize the playbook (body `{"approved_by": string}`; M1 and M4 both call this) |
| POST | `/api/incidents/{id}/reject` | Cancel the playbook |
| GET | `/api/incidents/{id}/audit` | (added, M2) Chronological audit log of playbook execution decisions |
| GET | `/api/incidents/{id}/postmortem` | Generated postmortem as markdown |
| GET | `/api/blast-radius/{service}` | Services and users affected if this one fails |
| POST | `/api/autonomy` | (added, M3) body {"level": 1-3}, returns {"level": n} |
| POST | `/api/tts` | (added, M3) body {"text": string}, returns `audio/wav` -- Gemini TTS for the voice briefing |
| WS | `/ws` | Live event stream |

Plus `GET /api/incidents/latest`, which the Telegram bot polls.

## Interfaces

These signatures are fixed in hour 0 so every member can code against them before the other side exists. Changing one needs a heads-up to whoever consumes it.

**Scenario file** (Member 4 writes, Members 2 and 3 read) — `backend/scenarios/db_oom.json`

```jsonc
{
  "id": "db_oom",
  "title": "Database out of memory",
  "root_service": "postgres",
  "duration_s": 12,
  "metrics": { "postgres": [ { "t_s": 0.0, "mem_mb": 40, "cpu_pct": 12 } ] },   // one point every 0.5 s
  "events":  [ { "t_s": 6.0, "service": "postgres", "text": "Reason: OOMKilled, Exit Code: 137" } ],
  "logs":    { "postgres": [ { "line": 42, "t_s": 6.0, "text": "FATAL: out of memory" } ] },   // ~50 lines per service
  "alerts":  [ { "t_s": 6.2, "service": "auth-service", "severity": "critical", "message": "connection refused: postgres:5432" } ],   // exactly 56
  "fix":     { "action": "patch_memory_limit", "from": "64Mi", "to": "256Mi" }
}
```

**Backend functions** (Python)

```python
# adapters/base.py — Member 2
class ClusterAdapter(Protocol):
    async def list_services(self) -> list[ServiceNode]: ...
    async def get_logs(self, service: str, lines: int = 50) -> list[LogLine]: ...
    async def get_metrics(self, service: str) -> list[MetricPoint]: ...
    async def get_events(self, service: str) -> list[K8sEvent]: ...
    async def apply_action(self, step: PlaybookStep) -> ActionResult: ...
    async def probe(self, service: str) -> bool: ...          # True when healthy

# graph.py — Member 2 (pure functions, unit-tested)
def find_root(alerting: set[str]) -> str
def impacted(root: str, alerting: set[str]) -> list[str]
def topo_order(services: list[str]) -> list[str]              # dependencies first
def blast_radius(service: str) -> list[str]                   # everything downstream

# bus.py — Member 2
async def emit(type: str, payload: dict) -> None              # wraps payload in the contract envelope

# agents/pipeline.py — Member 3 (Member 2 calls it when an incident opens)
async def run_pipeline(incident: Incident, adapter: ClusterAdapter) -> Incident
#   emits agent_step events; returns the incident with rca + playbook, status "awaiting_approval"

# agents/citations.py — Member 3
def verify_citations(rca: RCA, logs: list[LogLine], events: list[K8sEvent],
                     metrics: list[MetricPoint]) -> RCA

# agents/autonomy.py — Member 3
def needs_approval(step: PlaybookStep, level: int) -> bool

# executor.py — Member 2 (the approve endpoint calls it)
async def execute(incident: Incident, adapter: ClusterAdapter, approved_by: str) -> Incident
#   emits playbook_step + service_update; if a probe fails, rolls back that step and stops

# predictor.py — Member 2
def seconds_to_limit(points: list[MetricPoint], limit_mb: float) -> float | None

# agents/postmortem.py — Member 3
async def write_postmortem(incident: Incident) -> str         # markdown
```

**Frontend store** (TypeScript, zustand) — Member 1

```ts
type AppState = {
  services: Record<string, ServiceNode>;
  alerts: Alert[];
  incident: Incident | null;
  agentSteps: AgentStep[];
  stepStatus: Record<number, 'pending' | 'running' | 'done' | 'failed'>;
  metrics: Record<string, MetricPoint[]>;
  prediction: { service: string; seconds: number } | null;
  apply: (e: WsEvent) => void;   // the ONLY place events change state
  reset: () => void;
};
```

**Member 4's components and helpers** — Member 1 only mounts them

```tsx
<ReasoningPanel steps={agentSteps} />           // terminal style, typing effect, auto-scroll
<Stopwatch startedAt={incident?.started_at} resolvedAt={incident?.resolved_at} />
<CostTicker startedAt={incident?.started_at} resolvedAt={incident?.resolved_at}
            perMinute={Number(import.meta.env.VITE_COST_PER_MINUTE)} currency="₹" />
<PostmortemView incidentId={incident.id} />   // fetches /api/incidents/{id}/postmortem, renders, downloads .md

// lib/voice.ts
export function speak(text: string): void      // browser speechSynthesis; silent when muted
// lib/sounds.ts
export function playSiren(): void
export function playChime(): void
export function setMuted(muted: boolean): void
```

**Environment variables** (`.env`)

| Variable | Example | Used by |
| --- | --- | --- |
| `LLM_API_KEY`, `LLM_MODEL` | your key and chosen model | Member 3 |
| `GOOGLE_TTS_API_KEY` | Cloud Text-to-Speech API key (preferred; separate quota from `LLM_API_KEY`) | Member 3 |
| `TTS_MODEL` | `gemini-3.8-flash-tts` (default) -- fallback path, reuses `LLM_API_KEY` | Member 3 |
| `DEMO_MODE` | `auto` (live, cache on failure), `cache`, `live` | Member 3 |
| `AUTONOMY_LEVEL` | `2` | Member 3 |
| `ADAPTER` | `simulator` or `k8s` | Member 2 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | from BotFather and the group | Member 4 |
| `BACKEND_URL` | `http://localhost:8000` | Member 4 (bot) |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | Member 1 |
| `VITE_COST_PER_MINUTE` | a figure you can justify on stage | Member 4 |
