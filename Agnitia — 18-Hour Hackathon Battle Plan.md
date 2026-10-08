# Agnitia — 18-Hour Hackathon Battle Plan

Oct 8, 2026 · @33° Tilted

## 1. The strategy on one page

We win by showing something new and visual at every judging round, not by writing the most code. Judges score what they can see and understand in 2–3 minutes, so every hour goes into features that are visible on screen, easy to explain, and safe to demo.

**One-line pitch:** Agnitia is an AI on-call engineer. It turns a storm of 50+ alerts into one root cause with proof, builds a recovery plan in the safe order, and heals the system once a human approves.

**Five rules for the whole team**

1. **Simulator first, real Kubernetes second.** The built-in simulator gives a repeatable demo by hour 5. Real Kubernetes is a side track that proves one scenario works for real.
2. **Every round gets a new reveal.** Round 1: it detects and maps the failure. Round 2: the AI diagnoses and heals it with human approval. Final: phone approval, a self-written postmortem, and a crash predicted before it happens.
3. **Plant a promise, then keep it.** End each table visit with "next time you come by, you'll be able to …" and make it true. Judges remember teams that deliver on what they said.
4. **Theatre is a feature.** Pulsing nodes, a counting stopwatch, a voice briefing and a siren cost under an hour each and are what judges talk about afterwards.
5. **Never demo a broken build.** Freeze a tagged version before each round, and keep a one-click Reset that returns everything to green in 2 seconds.

**Assumed schedule** (shift the checkpoints if your hackathon announces different times):

| Round | When | What judges must see working |
| --- | --- | --- |
| Checkpoint 1 | \~Hour 5 | Click "Inject fault" → graph turns red and amber → 56 alerts collapse into 1 incident |
| Checkpoint 2 | \~Hour 11 | Full loop: AI root cause with evidence → ordered playbook → approval → system heals |
| Final | Hour 17.5–18 | Polished story plus phone approval, voice briefing, postmortem, crash prediction, real-K8s proof |

## 2. What changes from the 24-hour plan

The core idea stays the same; what changes is the build order and the extras. With 6 fewer hours, we build what judges see first and what sits underneath second.

| Area | 24-hour plan | 18-hour plan |
| --- | --- | --- |
| Build order | Backend and AI first, polish late | Visual skeleton plus simulator first, so Checkpoint 1 already looks finished |
| Real Kubernetes | Equal priority with simulator | Side track for one scenario (database out of memory), plus a backup video |
| Prometheus / Grafana | Implied real metrics stack | Cut. The simulator generates realistic metric curves; same chart on screen |
| Person 4 | Chaos scenarios, then pitch at the end | Table host for every judge visit, plus phone-approval bot, real-K8s track and deck |
| Pitch prep | Hours 21–24 | Rolling: a short deck update before each checkpoint, final rehearsal from hour 16 |
| Wow features | Graph, evidence, approval | Plus phone approval, voice briefing, live AI reasoning, auto-postmortem, crash prediction, incident memory |
| Demo safety | Simulator mode | Plus a Reset button, cached AI answers, frozen git tags and a backup recording |

**Three fixes to the original plan before anyone builds:**

- **One alert number everywhere.** The plan says 56 alerts in one place and 38 in the demo script. Pick 56 and make the simulator emit exactly 56.
- **Don't say "zero hallucinations".** One sharp judge question breaks it. Say "every claim cites a real log line, and we check each citation against the raw logs automatically." That is stronger, and true once built (see Feature 13).
- **Frame the time saving honestly.** Say "in this scenario, time to recovery went from about 45 minutes of manual digging to under a minute." A claim you can defend beats a bigger one you can't.

## 3. Feature menu, ranked by wow per hour

Build all 7 Tier 1 features, at least 6 of Tier 2, and 3 or more of Tier 3. Effort assumes one person working with Claude or Antigravity; anything over 2 hours is a side track, not a blocker.

**Tier 1 — the core story (must work by Checkpoint 2)**

| # | Feature (what judges see) | Brag line on stage | Effort | First shown |
| --- | --- | --- | --- | --- |
| 1 | Live dependency map: 6 services, root cause pulses red, victims turn amber, edges animate | "A live map of how every service depends on every other" | 2 h | Checkpoint 1 |
| 2 | Chaos panel: one-click faults (database out of memory, bad config crash loop, CPU spike) | "Built-in chaos engineering to test it live" | 1 h | Checkpoint 1 |
| 3 | Alert storm funnel: 56 alerts pour in and collapse into 1 incident card, "98% noise removed" | "Graph-aware alert correlation, not just time-based grouping" | 1.5 h | Checkpoint 1 |
| 4 | Evidence drawer: highlighted log lines, memory-spike chart, exit code 137, confidence score | "Every diagnosis comes with proof" | 2 h | Checkpoint 2 |
| 5 | Ordered playbook: database first, wait for health check, then dependants | "Recovers in dependency order, so nothing crashes twice" | 1 h | Checkpoint 2 |
| 6 | Approval card with a before/after config diff (64Mi → 256Mi) and an Authorize button | "Human-in-the-loop safety gate for risky changes" | 1.5 h | Checkpoint 2 |
| 7 | Healing animation: nodes go green one by one as health checks pass | "Self-healing with automatic verification" | 1.5 h | Checkpoint 2 |

**Tier 2 — wow multipliers (cheap and theatrical)**

| # | Feature (what judges see) | Brag line on stage | Effort | First shown |
| --- | --- | --- | --- | --- |
| 8 | Live AI reasoning panel: a terminal that prints the agent's steps as they happen | "Watch the AI investigate in real time" | 1 h | Checkpoint 1 (scripted), 2 (live) |
| 9 | Agent pipeline strip: Triage → Diagnose → Plan → Execute → Verify chips light up in turn | "A five-agent architecture" (each agent is one function with its own prompt) | 1 h | Checkpoint 2 |
| 10 | Phone approval: the incident card arrives in Telegram with Approve / Reject buttons; a judge scans a QR code and approves | "Approve a production fix from anywhere" | 1.5 h | Checkpoint 2 |
| 11 | Voice briefing: the browser reads the incident summary aloud | "Hands-free on-call briefing at 3 AM" | 30 min | Final |
| 12 | Recovery stopwatch plus a downtime-cost counter | "Recovered in 38 seconds; ₹X of downtime avoided" | 30 min | Checkpoint 2 |
| 13 | Citation verifier: each cited log line is checked against the raw logs and gets a Verified badge | "A hallucination guard: if the AI invents evidence, we catch it" | 45 min | Checkpoint 2 |
| 14 | One-click postmortem: a full incident report with timeline, cause and action items, downloadable | "From incident to postmortem in 10 seconds" | 1 h | Final |
| 15 | What-if blast radius: click any healthy service to see what would break and how many users | "Predictive blast-radius analysis" | 1 h | Final |

**Tier 3 — innovation claims (sound advanced, still feasible)**

| # | Feature (what judges see) | Brag line on stage | Effort | First shown |
| --- | --- | --- | --- | --- |
| 16 | Crash prediction: a slow memory leak triggers "Database runs out of memory in 3m 40s" before it crashes, with a one-click preventive fix | "We fix it before it breaks" | 1.5 h | Final |
| 17 | Incident memory: "Matches INC-087, 94% similar; the same fix worked last time" | "It learns from every incident" | 1.5 h | Final |
| 18 | Autonomy levels: low-risk actions run on their own, high-risk ones wait for a human; a 1–3 slider sets the policy | "Policy-driven autonomy, like a self-driving car's levels" | 1 h | Final |
| 19 | Real Kubernetes mode: the same out-of-memory scenario on a local kind cluster, toggled in the UI, plus a backup video | "It runs on real clusters, not just a mock-up" | 3–4 h side track | Final |
| 20 | MCP server: Claude Desktop or any AI assistant can ask Agnitia for incidents and request fixes | "AI-native: any assistant can operate it" | 1–1.5 h | Final (stretch) |
| 21 | Ask Agnitia chat: "Why did payments fail?" answered from the incident data | "Talk to your infrastructure" | 1 h | Final (stretch) |

**Skip entirely:** a real Prometheus/Grafana stack, login and accounts, a database, multi-cluster support, Slack approve buttons (workspace app setup eats time; a Telegram bot takes 5 minutes), voice commands (a noisy hall breaks them), and any custom ML model. Each costs hours and shows nothing new on screen.

## 4. Round-by-round plan

Each round has one headline reveal, a short list of features that must work, and a promise for the next visit. Person 4 hosts every judge visit so the builders never stop coding.

**At every intermediate round**

- The demo runs on a dedicated laptop that nobody codes on during judging windows, always parked on the all-green start screen.
- A second screen shows a progress board: Done / Building now / Next, with the feature names from section 3. Visible velocity scores points on its own.
- The host gives the 60–90 second table pitch (section 12), runs the live demo, then names the promise for next time.

### Round 0 — opening idea pitch (only if your hackathon has one)

- **Show:** the problem in one sentence, the 5-step flow (Detect → Correlate → Diagnose → Plan → Approve & Heal), and the checkpoint roadmap.
- **Why the roadmap:** judges come back to your table looking for the things you promised.

### Checkpoint 1 (\~hour 5) — "It sees the problem"

- **Must work:** Features 1, 2, 3, scripted 8, the Reset button, and an incident card with a pre-written root cause.
- **Demo (60 s):** click "Inject database out of memory" → alerts pour in and collapse into INC-104 → the map shows the database red and 4 services amber → the reasoning panel prints its investigation steps.
- **Slides (4):** the 3 AM problem, the 5-step flow, architecture, progress board.
- **Promise:** "Next time, the AI will prove the cause and fix it, but only after you approve."
- **Freeze:** git tag `cp1` on a working build before the judges arrive.

### Checkpoint 2 (\~hour 11) — "It fixes the problem, safely"

- **Must work:** Features 4, 5, 6, 7, 9, 12, 13 with the live AI (cached answer as fallback); Feature 10 if ready.
- **Demo (90 s):** inject → evidence drawer with Verified badges → ordered playbook → approval diff → Authorize → nodes go green in order → stopwatch stops. If the phone bot works, hand the judge the phone to approve.
- **Slides:** add the agent pipeline and a safety slide (approval gate, allow-listed actions, audit log).
- **Promise:** "In the final, it will predict this crash before it happens and write its own postmortem."
- **Freeze:** git tag `cp2`.

### Final (hour 17.5–18) — "It's a product"

- **Must work:** all of Tier 1 and Tier 2, plus Features 16 and 18, ideally 17, and the real-Kubernetes clip (Feature 19).
- **Demo:** the full script in section 11, with a judge approving on the phone if the room allows.
- **Slides:** the full deck in section 13.
- **Freeze:** feature freeze at hour 15, git tag `final`; after that, only bug fixes and rehearsal.

## 5. The 18-hour timeline

The build runs in five phases separated by four gates; each lane has to land something visible before every gate.

&#91;embedded content: 18-hour build plan · 4 lanes, 5 phases, 4 gates\]

Read each row as one phase and each column as one person. Detailed checklists are in section 6; what each checkpoint must show is in section 4.

## 6. Team roles, task checklists and AI tool split

Four people, four lanes, one shared contract. Each person ticks off their own checklist; feature numbers refer to section 3.

**How to split the AI tools**

- **Antigravity → Person 1 (frontend).** It is strongest at generating whole screens and multi-file UI changes, and its browser agent can click through the app to test it.
- **Claude → Persons 2, 3 and 4.** Backend logic, the simulator, prompts and schemas, debugging, deck text and scripts.
- **Paste `CONTRACT.md` (section 7) at the top of every new AI session.** This one habit stops four AI sessions from inventing four different data formats.
- **Ask for small, testable pieces:** one component or one endpoint per prompt, run it, commit, move on.
- **Pro plans have usage caps.** Don't spend Claude on boilerplate CSS; if an AI loops on the same bug for 15 minutes, switch tools or ask a teammate.

### Person 1 — Frontend lead (Antigravity)

- [ ] H0–1: Scaffold Vite + React + Tailwind + React Flow, dark theme, layout (map left, panels right, chaos bar bottom)
- [ ] H1–3: Dependency map with 4 node states (healthy, root cause, impacted, recovering), pulse and animated edges (F1)
- [ ] H3–4.5: Chaos panel, alert-storm funnel with counter, incident card, reasoning-panel shell, Reset button (F2, F3, F8)
- [ ] H4.5–5: Wire WebSocket events end to end; tag `cp1`
- [ ] H5–7.5: Evidence drawer: log viewer with highlighted lines, memory chart, Verified badges (F4, F13)
- [ ] H7.5–10: Playbook card, approval modal with diff, healing animation, agent strip, stopwatch (F5, F6, F7, F9, F12)
- [ ] H11–13: Voice briefing, prediction banner, what-if click mode, autonomy slider (F11, F15, F16, F18)
- [ ] H13–15: Postmortem viewer, sound and motion polish, check on a projector-sized screen
- [ ] H15–16: Bug fixes only

### Person 2 — Backend and simulator (Claude)

- [ ] H0–1: FastAPI + WebSocket skeleton; co-write `CONTRACT.md`
- [ ] H1–4.5: Simulator with the 6-service graph and 3 fault scenarios, emitting exactly 56 alerts plus metrics and logs; topological correlation; Reset endpoint
- [ ] H4.5–5: Integration with Person 1
- [ ] H5–10: Playbook executor (steps in order, waits for each health probe), audit log, incident timeline, blast-radius endpoint
- [ ] H10–11: Integration; tag `cp2`
- [ ] H11–15: Slow-leak scenario and crash prediction (F16), autonomy rules (F18), plug in Person 4's real-K8s adapter (F19), MCP server if time allows (F20)
- [ ] H15–16: Bug fixes only

### Person 3 — AI agent (Claude)

- [ ] H0–1: LLM API key working; one structured-output test call returning valid JSON
- [ ] H1–4.5: Root-cause prompt and schema, tested on each scenario's logs; save one cached answer per scenario; scripted reasoning steps for Checkpoint 1
- [ ] H4.5–5: Integration
- [ ] H5–10: Live pipeline Triage → Diagnose → Plan → Verify; stream reasoning steps; citation verifier (F13); risk tag on every playbook step
- [ ] H10–11: Integration
- [ ] H11–15: Postmortem generator (F14), incident memory (F17), Ask Agnitia chat if time allows (F21)
- [ ] H15–16: Refresh cached answers for every scenario from the final build

### Person 4 — Chaos content, proof track and pitch (Claude + terminal)

- [ ] H0–1: Write scenario content: realistic logs, the 56 alert messages, metric curves for all 3 faults; hand to Persons 2 and 3
- [ ] H1–4.5: Checkpoint 1 deck (4 slides), progress board, table pitch script
- [ ] H5: Host Checkpoint 1
- [ ] H5–8: Telegram approval bot with Approve / Reject buttons and a join QR code (F10)
- [ ] H8–10: Local kind cluster: Postgres with a 64Mi limit plus a memory hog; scripted patch and rollout restart
- [ ] H11: Host Checkpoint 2
- [ ] H11–14: Finish the real-K8s scenario and record it as a clip (F19); final deck
- [ ] H14–16: Record a full backup demo video; write the Q&A sheet
- [ ] H16–17.5: Lead rehearsals and time every run

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
    "similar_incident": { "id": "INC-087", "similarity": 0.94 }   // Feature 17, optional
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
| POST | `/api/incidents/{id}/approve` | Authorize the playbook (UI button and Telegram bot both call this) |
| POST | `/api/incidents/{id}/reject` | Cancel the playbook |
| GET | `/api/incidents/{id}/postmortem` | Generated postmortem as markdown |
| GET | `/api/blast-radius/{service}` | Services and users affected if this one fails |
| WS | `/ws` | Live event stream |

Plus `GET /api/incidents/latest`, which the Telegram bot polls.

## 8. Architecture and tech stack

One FastAPI backend sits between the screen and a swappable cluster adapter; the five "agents" are five functions in one pipeline, which is what makes them buildable in a day.

&#91;embedded content: Agnitia architecture · 3 layers, 5 agents, 3 outside services\]

Each guard sits under the agent it protects: the verifier checks Diagnose, the human gate stops Plan, and the allow-list limits Execute. Swapping the simulator for real Kubernetes changes nothing above the adapter.

| Layer | Tool | Why this one |
| --- | --- | --- |
| Frontend | React + Vite + Tailwind | Antigravity generates it fast; hot reload while you tweak visuals |
| Dependency map | React Flow (`@xyflow/react`) | Custom nodes, animated edges and dragging out of the box |
| Motion and charts | Framer Motion, Recharts | Alert funnel and pulse animations; the memory-spike chart |
| Approval diff | A React diff-viewer library | Before/after config in two lines of code |
| Backend | Python FastAPI + Uvicorn | Async and WebSockets built in; Pydantic models mirror the contract |
| AI | Any LLM API with JSON output | Diagnose, plan and postmortem prompts, temperature 0, cached answers |
| Phone approval | Telegram bot, async python-telegram-bot, long polling | Bot token in 5 minutes, no public URL |
| Real cluster | kind + Kubernetes Python client | One-command local cluster for the proof clip |
| Voice briefing | Browser speech synthesis (Web Speech API) | No key, no install, one function call |
| MCP (stretch) | MCP Python SDK | Lets Claude Desktop query Agnitia |

**API key, hour 0:** your Claude Pro and Antigravity plans pay for the coding tools, not for the AI calls inside your product. Get an API key before you start: Google AI Studio has a free Gemini tier (check its current limits), or use any API credits the team already has.

## 9. Copy-paste starter prompts

These prompts get each lane from blank folder to working feature fastest. Always paste `CONTRACT.md` above them, then iterate in small steps.

**P1 — Map and layout (Antigravity)**

```text
Read CONTRACT.md. Build a React + Vite + Tailwind app called Agnitia with a dark mission-control theme.
Left 60%: a React Flow (@xyflow/react) dependency map of the 6 services, laid out left to right by tier.
Custom node: label, tier, a memory bar, and a status colour — healthy green, root_cause red with a pulsing
glow, impacted amber, recovering blue. Edges animate and turn red when their target is root_cause or impacted.
Right 40%: stacked panels for Incident, AI Reasoning (terminal style, monospace, auto-scroll) and Timeline.
Bottom bar: one button per chaos scenario plus Reset. Connect to ws://localhost:8000/ws and update state from
the event types in CONTRACT.md. If the socket is down, replay mock events from a local JSON file.
```

**P1 — Alert storm funnel (Antigravity)**

```text
Add an AlertStorm component. As alert events arrive, show each as a small card dropping into a funnel shape
(framer-motion) with a large live counter. When the incident_update arrives, collapse all cards into one
incident card labelled with the incident id and show "56 alerts -> 1 incident (98% noise removed)".
```

**P2 — Backend and simulator (Claude)**

```text
Read CONTRACT.md. Write a FastAPI app with the WebSocket and REST endpoints listed. Implement an in-process
simulator with the 6-service graph and scenarios db_oom, bad_config, cpu_spike, slow_leak.
For db_oom: ramp postgres memory from 40Mi to 64Mi over 6 s (metric_point every 500 ms), mark it OOMKilled,
then emit exactly 56 alerts over 3 s using the per-service counts in CONTRACT.md. Apply the correlation rule
and emit incident_update. Every scenario must be deterministic: same click, same events.
/api/reset restores everything and emits a reset event. Put the simulator behind an interface
(get_logs, get_metrics, get_events, apply_action) so a real Kubernetes adapter can replace it later.
```

**P3 — Diagnosis agent system prompt (goes inside the product)**

```text
You are Agnitia's diagnosis agent, an expert Kubernetes SRE. You receive the root service, its last 50 log
lines with line numbers, Kubernetes events, and memory and CPU metrics. Find the root cause.
Rules: every claim must cite evidence copied exactly from the input, with its line number or timestamp.
If the evidence does not support a cause, say "insufficient evidence" and lower your confidence.
Never invent log lines, numbers or events. Respond only with JSON matching the rca schema.
```

**P3 — Planner agent system prompt**

```text
Given the root cause and the dependency graph, produce a recovery playbook using ONLY these actions:
patch_memory_limit, patch_cpu_limit, rollout_restart, rollback_deployment, scale_replicas, wait_for_ready,
verify_health. Order steps so every dependency is healthy before its dependants restart. Mark any resource
or config change as risk "high" with requires_approval true. Respond only with JSON matching the playbook schema.
```

**P3 — Citation verifier (Claude)**

```text
Write verify_citations(rca, raw_logs, events, metrics). Mark each evidence item verified=true only if its text
appears (ignoring whitespace) in the raw source it claims to come from. If any citation fails, lower
confidence by 0.2 and add a warning field the UI can show.
```

**P4 — Telegram approval bot (Claude)**

```text
Write a bot with the async python-telegram-bot library using long polling (no webhook, no public URL).
Every 2 s it polls GET /api/incidents/latest. When a new incident reaches awaiting_approval, it posts to a
configured group: incident id, root cause, impacted services, the config diff, and inline buttons
Approve and Reject. On tap it calls the approve or reject endpoint and edits the message to show who
approved and when.
```

**P2 — Crash prediction (Claude)**

```text
Add predict_exhaustion(points, limit): fit a linear trend to the last 20 memory points; if the slope is
positive, return the seconds until the limit is reached. Emit a prediction event when that drops below
300 s, update it every second, and offer the playbook early as a preventive fix.
```

**P3 — Postmortem writer (Claude, inside the product)**

```text
Write a blameless postmortem in markdown from this incident JSON: Summary; Impact (services, duration);
Timeline; Root cause with the cited evidence; Resolution steps; What went well; 3 action items, each with an
owner role. Under 400 words. Use only facts present in the JSON.
```

## 10. Demo safety net

The demo must survive no Wi-Fi, a slow AI API, a broken commit and a tired team. Build the first four nets before Checkpoint 1 and keep them to the end.

| Risk | Safety net | Owner |
| --- | --- | --- |
| Wi-Fi drops or the AI API is slow | Demo mode: if a live AI call fails or takes over 4 s, replay the cached answer for that scenario. Same screen, nobody can tell | Person 3 |
| AI answers differently on stage | Temperature 0, deterministic scenario logs, cached answers refreshed from the final build | Person 3 |
| A broken commit right before judging | The demo laptop runs the frozen tag (`cp1`, `cp2`, `final`); nobody pulls during judging windows | Everyone |
| Judges arrive back to back | Reset button: all green in 2 s, full mini-demo again in 60 s | Persons 1, 2 |
| Telegram fails or the judge has no Telegram | Presenter's phone already in the group; the on-screen Authorize button always works too | Person 4 |
| Real Kubernetes misbehaves | Run it live only if it passed 10 of 10 rehearsals; otherwise play the recorded clip | Person 4 |
| Laptop or projector trouble | Second laptop on the same build; backup video on a USB stick and a phone; HDMI adapter tested at the venue | Person 4 |
| Text unreadable on the projector | Test at 1920×1080; no panel text under 16 px | Person 1 |
| Exhaustion | Staggered 45-minute naps between hours 12 and 15, never two builders asleep at once | Everyone |

**Rehearsal rule:** run the full demo 10 times between hours 16 and 17.5. Any step that fails twice gets cut or switched to cached mode.

**Just before going on stage:** make one warm-up AI call, open every tab you need, turn on Do Not Disturb, close chat apps, and press Reset.

## 11. Final presentation demo script (3 minutes)

Two people on stage: the Speaker talks, the Driver clicks on cue words and never speaks. The third teammate handles the phone approval; the fourth watches the backend and switches to cached mode if anything stalls.

| Time | On screen (Driver) | Speaker says |
| --- | --- | --- |
| 0:00–0:20 | Title slide | "It's 3 AM. Your database runs out of memory. Your phone doesn't buzz once; it buzzes 56 times. Every service is screaming, and you can't tell which alert is real. Engineers lose 30 to 60 minutes just finding the cause." |
| 0:20–0:35 | Switch to Agnitia, everything green | "Meet Agnitia, an AI on-call engineer. It finds the real problem, proves it, and fixes it safely, with a human in control." |
| 0:35–1:00 | Click **Inject database out of memory**; memory bar fills, siren, alerts pour into the funnel | "We just injected a real failure. 56 alerts. Agnitia reads them against the dependency map: the database is red, the root cause. These four services are amber, just victims. Redis is green, untouched, so it's left out. 56 alerts, one incident." |
| 1:00–1:30 | Reasoning panel streams, agent strip lights up, voice briefing plays, open the evidence drawer | "Five agents work in sequence: triage, diagnose, plan, execute, verify. Here's the proof: exit code 137, the fatal log line at line 42, memory hitting its 64-megabyte limit. Every citation is checked against the raw logs; that's the Verified badge. And it has seen this before: a 94% match with incident 87." |
| 1:30–2:00 | Playbook card, then the approval diff; the incident card buzzes on the phone | "A panicked engineer restarts everything at once, and it all crashes again. Agnitia fixes in order: database first, wait for its health check, then everything that depends on it. Raising memory is risky, so it stops and asks a human. Judge, you're on call tonight. Tap Approve." |
| 2:00–2:25 | Nodes turn green one by one; stopwatch stops | "Memory raised. Database healthy. Services restarting… all green. Recovered in 38 seconds in this scenario, against about 45 minutes by hand." |
| 2:25–2:40 | Click **Generate postmortem** | "And the job every engineer hates, the postmortem, written in 10 seconds with the timeline and the evidence." |
| 2:40–2:55 | Click **Inject slow memory leak**; prediction banner counts down | "But the best incident is the one that never happens. This is a slow leak. Agnitia spotted the trend and warns us minutes before the crash, with the fix ready." |
| 2:55–3:00 | Closing slide | "Agnitia: from 56 alerts to one verified fix, safely. Thank you." |

**If you have 5 minutes,** add in this order: the architecture slide (40 s), the real-Kubernetes clip (20 s), a what-if click on Redis to show its blast radius (20 s), and who would pay for this (40 s).

**If something breaks live,** the Speaker says "Live demos at 3 AM, which is exactly why we built a safe mode," the backend watcher switches to cached mode, and you carry on. Rehearse this line so it sounds calm.

## 12. Intermediate round table pitches

At the table, start the demo within 15 seconds and always say what is new since the judge's last visit. Person 4 delivers these; the builders keep coding.

**Checkpoint 1 — 60 seconds**

> "Hi, we're building Agnitia, an AI on-call engineer for cloud systems. When one database fails, engineers get 50-plus alerts from every service that depends on it and lose most of an hour finding the real cause. *(Click Inject.)* Here's a live failure: 56 alerts. Agnitia collapses them into one incident by reading the dependency map. Red is the root, amber are the victims, and the reasoning panel shows how it got there. In five hours we built the live map, the chaos engine and graph-based alert correlation. Next, the AI proves the cause with real log evidence and fixes it, but only after a human approves. Next time you visit, you'll press that button."

**Checkpoint 2 — 90 seconds**

> "Welcome back. Last time Agnitia could see the problem; now it fixes it. *(Click Inject.)* Same failure, 56 alerts, one incident. Five AI agents take over. Here's the evidence: exit code, the fatal log line, the memory spike, each verified against the raw logs. It plans the recovery in dependency order so nothing crashes twice, and because it's changing memory limits, it waits for a human. *(Hand over the phone.)* You're on call. Tap Approve. *(Nodes turn green.)* Recovered, in order, in 38 seconds. Since your last visit we added the agent pipeline, citation checks, the approval gate and phone approval. In the final, it predicts this crash before it happens and writes its own postmortem."

**Table host habits**

- Let the judge click Inject or Approve. Touching the demo makes it memorable.
- Answer each question in one sentence, then show the answer on screen.
- Write down every judge question and mentor tip; fix it or prepare an answer before the next round, then say "you suggested X, here it is."

## 13. Pitch deck outline (12 slides)

Every slide must make sense to a judge with zero cloud background. The headline is a full sentence stating the takeaway, there is one visual per slide, and any jargon is explained on the slide where it first appears.

1. **"Agnitia: the AI on-call engineer that finds the real problem and fixes it safely."** Logo, team name.
2. **"When one service fails, engineers get 56 alerts, not one."** A phone flooded with notifications beside the failure chain: database → login → payments → gateway → website.
3. **"Finding the cause takes 30–60 minutes, and the wrong fix makes it worse."** Three pains: alert storm, slow manual digging, restarts that crash again.
4. **"Agnitia closes the loop in five steps."** Detect → Correlate → Diagnose → Plan → Approve and Heal, one plain line each.
5. **"Live demo."** Switch to the app.
6. **"Five AI agents, one dependency map, and a human in control."** The architecture diagram from section 8.
7. **"Every claim comes with proof the AI can't fake."** Evidence drawer screenshot with Verified badges. Footnote: "Exit code 137 = the system stopped the program for using too much memory."
8. **"The AI can only do what we allow, and it asks before anything risky."** Allow-list, approval gate, autonomy levels, audit log.
9. **"In our test scenario: 56 alerts became 1 incident, and recovery took 38 seconds instead of about 45 minutes."** Two big numbers.
10. **"Others group alerts or explain errors; Agnitia also fixes them in the right order."** Comparison grid (see section 14).
11. **"Built for teams running Kubernetes without a 24/7 reliability team."** Who pays, plus the roadmap: auto-discovered dependency maps, more fault types, Slack and PagerDuty.
12. **"Built in 18 hours."** Team photo and roles, thank you, QR code to the demo video.

**Deck timeline:** slides 1–4 and a progress board for Checkpoint 1; add 6–8 for Checkpoint 2; the full deck from hour 14.

## 14. Judge Q&A prep

The toughest question will be "doesn't this already exist?", because in 2026 it partly does. Answer it head-on: big vendors entering the space proves the problem is real, and our angle is the complete loop, light enough for a small team.

**What the market looks like (know this before the final)**

- Dynatrace already does topology-aware root cause analysis on a live dependency graph, with automated remediation through workflows; Komodor's Klaudia runs multi-agent Kubernetes remediation with self-learning memory ([NeuBird, Apr 2026](https://neubird.ai/blog/top-ai-sre-tools)).
- PagerDuty added an SRE Agent in spring 2026; BigPanda specialises in alert noise reduction; Metoro offers Kubernetes AI SRE from about $20 per node per month ([same source](https://neubird.ai/blog/top-ai-sre-tools)). That list is written by a competitor (NeuBird), so treat its rankings as marketing.
- LangChain published how it built its own Kubernetes SRE agent where a human approves fixes from Slack ([LangChain, Aug 2026](https://langchain.com/blog/how-we-build-an-autonomous-sre-agent-for-kubernetes-deployments)). The human-approval pattern is now mainstream, so present it as good practice, not as the invention.

**Comparison grid for slide 10** (categories, not attacks on named products)

| Capability | Alert managers | Enterprise observability AI | Agnitia |
| --- | --- | --- | --- |
| Groups an alert storm into one incident | Yes | Yes | Yes, by the dependency graph |
| Root cause with cited, machine-checked evidence | Mostly no | Partly | Yes, every citation verified |
| Multi-step recovery in dependency order | No | Via custom workflows | Built in |
| Needs its own full observability stack | No | Yes, and priced per host or GB | No; reads Kubernetes directly |
| Predicts the crash before it happens | Rarely | Some | Yes, for resource exhaustion |

**Likely questions and one-breath answers**

1. **"Is this real Kubernetes or a simulation?"** "Both. The simulator keeps the stage demo reliable; the same engine runs the out-of-memory scenario on a real kind cluster, and here's the clip." Never imply the simulator is production.
2. **"What if the AI is wrong?"** "Three guards: every citation is checked against the raw logs, low confidence blocks automation, and any risky change needs a human approval with a visible diff."
3. **"How do 56 alerts become one?"** "A service is the root if none of its dependencies are alerting; every alerting service downstream joins its incident. Redis stayed green, so it was correctly left out."
4. **"Where does the dependency map come from?"** "Today, a config file. Next, auto-discovery from service-mesh or OpenTelemetry traffic."
5. **"Doesn't Dynatrace or Komodor already do this?"** "Parts of it, inside expensive enterprise platforms. Agnitia is the full loop (group, prove, plan in order, approve, heal) for a five-person startup with no reliability team."
6. **"Is giving an AI write access safe?"** "It can only run 7 allow-listed actions, none of which delete anything; risky ones need approval, and every action lands in an audit log."
7. **"Does it scale to 500 services?"** "The graph logic is a linear walk over services and dependencies, so the map grows fine; the AI only ever reads the root service's evidence, not all 500."
8. **"Which model, and what does an incident cost?"** Know your model name and measure the tokens per incident during rehearsal, so you can quote a real number.
9. **"How is the prediction done?"** "A linear trend on the memory curve, honest and explainable. Seasonal and multi-signal models are on the roadmap."
10. **"What if the fix doesn't work?"** "The verify step checks health after each step; if a check fails, it stops, rolls back that step and pages a human."
11. **"Who pays?"** "Teams running Kubernetes without a 24/7 reliability team: per-cluster pricing, starting with Indian SaaS startups."
12. **"What did you build here versus before?"** Answer exactly and honestly; judges check commit history.

## 15. Brag sheet

Every claim below is true once its feature is built and visible on screen; claim nothing you can't show. Measure the timings during rehearsal and quote your measured numbers, not these placeholders.

| Say this on stage | Proof on screen | Feature |
| --- | --- | --- |
| "56 alerts became 1 incident: 98% less noise" | Alert funnel counter | 3 |
| "Root cause in seconds, with verified evidence" | Reasoning panel timestamps, Verified badges | 4, 13 |
| "Five specialised AI agents" | Agent pipeline strip | 9 |
| "Recovery in dependency order, so nothing crashes twice" | Playbook order and healing animation | 5, 7 |
| "Recovered in 38 seconds in this scenario, against about 45 minutes by hand" | Stopwatch | 12 |
| "Approve a production fix from your phone" | Telegram card in a judge's hand | 10 |
| "Postmortem written in 10 seconds" | Postmortem button | 14 |
| "It predicts the crash minutes ahead" | Prediction countdown | 16 |
| "It learns from past incidents" | "94% match with INC-087" | 17 |
| "It runs on real Kubernetes" | kind cluster clip | 19 |
| "Any AI assistant can operate it through MCP" | Claude Desktop asking Agnitia for incidents | 20 |

**Words that land:** evidence-backed, graph-aware, dependency-ordered, human-in-the-loop, verified, allow-listed.

**Words to avoid:** zero hallucinations, fully autonomous, production-ready, first ever. Each invites a question you can't win.

## Sources

- [Top 20 AI SRE Tools in 2026](https://neubird.ai/blog/top-ai-sre-tools), NeuBird, April 2026 (vendor-written comparison)
- [How we build an autonomous SRE Agent for Kubernetes Deployments](https://langchain.com/blog/how-we-build-an-autonomous-sre-agent-for-kubernetes-deployments), LangChain, August 2026. Its agent is open source; its read-only-by-default design with narrow, approval-gated write tools is worth citing as industry validation of Agnitia's allow-list.
