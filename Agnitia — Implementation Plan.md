# Agnitia — Implementation Plan

Oct 8, 2026 · @33° Tilted

## How this plan works

Four members build at the same time because each one owns separate folders and connects to the others only through the shared contract and six planned handoffs. This plan replaces the task split in the battle plan (sections 5 and 6); the contract, prompts, demo script and safety net there still apply.

**Five ground rules**

1. **Own your folders.** Edit another member's files only after asking them in the team chat.
2. **Build against the contract, not against each other.** Until the real piece arrives, use the mock data. Nobody waits for anybody.
3. **Done means tested.** A task is done when its "Done when" check passes from `make dev` and still works after pressing Reset.
4. **Main always runs.** Small commits, pull every 30 minutes, never push something that breaks `make dev`.
5. **Keep the Status column current.** It is how the team sees progress, and Member 4 turns it into the progress board judges see.

## Ownership map

Each member owns one layer end to end, and pairs with a review buddy who checks their merges and is the first person they ask when stuck.

| Member | Owns | Main tools | Review buddy |
| --- | --- | --- | --- |
| Member 1 — Frontend | App layout, state store, WebSocket client, dependency map, alert funnel, evidence drawer, approval flow, healing animation, prediction banner, what-if mode | Antigravity | Member 2 |
| Member 2 — Backend and simulator | FastAPI app, event bus, graph logic, simulator, playbook executor, crash predictor, real-Kubernetes adapter, smoke test | Claude | Member 1 |
| Member 3 — AI agents | Agent pipeline, prompts, citation verifier, demo-mode cache, autonomy rules, postmortem writer, incident memory, MCP server | Claude | Member 4 |
| Member 4 — Content and integrations | Scenario data files, mock event stream, reasoning panel, Telegram approval bot, stopwatch and cost ticker, voice and sound, postmortem view, decks, progress board, rehearsal log, backup video | Claude + Antigravity | Member 3 |

**Presentation roles** stay as in the battle plan: Member 4 hosts judge visits at the table; for the final, pick the Speaker and Driver by who rehearses best.

## Handoffs

Only six things cross from one member to another; everything else stays inside its owner's folders, which is what lets four people build side by side without collisions.

&#91;embedded content: handoffs between members · 6 connections, with due hours\]

Member 4's scenario files are the first handoff (hour 1), so they unblock both the simulator and the AI agents. Until each arrow lands, the receiver works from mock data.

## Repo layout

One repo, with every folder owned by exactly one member; the initials after each path name the owner. Shared files (marked `shared`) change only after a heads-up in the team chat.

```text
agnitia/
├── CONTRACT.md                     shared  (schemas, events, endpoints — battle plan §7)
├── README.md                       M4      (how to run, demo steps)
├── Makefile                        M2      (setup, dev, demo, test, reset)
├── .env.example                    M2
├── backend/
│   ├── main.py                     M2      FastAPI app, REST routes, /ws
│   ├── bus.py                      M2      emit() — broadcasts events to every socket
│   ├── models.py                   shared  Pydantic models mirroring CONTRACT.md (M2 edits, M3 requests)
│   ├── graph.py                    M2      find_root, impacted, topo_order, blast_radius
│   ├── executor.py                 M2      runs playbook steps in order, audit log
│   ├── predictor.py                M2      time-to-exhaustion from memory trend
│   ├── adapters/
│   │   ├── base.py                 M2      ClusterAdapter interface
│   │   ├── simulator.py            M2      plays scenario files deterministically
│   │   └── k8s.py                  M2      real kind cluster (phase 3)
│   ├── scenarios/                  M4      db_oom.json, bad_config.json, cpu_spike.json, slow_leak.json
│   ├── agents/
│   │   ├── pipeline.py             M3      triage → diagnose → plan → verify, demo-mode fallback
│   │   ├── diagnose.py  planner.py M3
│   │   ├── citations.py            M3      verify_citations()
│   │   ├── autonomy.py             M3      levels 1–3, which steps need approval
│   │   ├── postmortem.py           M3
│   │   ├── memory.py               M3      similar-incident matching
│   │   ├── past_incidents.json     M4      5 hand-written past incidents
│   │   ├── prompts/                M3      one .txt per agent
│   │   └── cache/                  M3      cached answers per scenario
│   ├── mcp_server.py               M3      stretch
│   └── tests/                      M2, M3  pytest per module
├── bot/
│   └── telegram_bot.py             M4      approval bot, long polling
├── frontend/src/
│   ├── store.ts  ws.ts             M1      state + reducer, socket with mock replay
│   ├── mock/events_db_oom.json     M4      full event stream for one run
│   ├── components/                 M1      DependencyMap, ServiceNode, ChaosPanel, AlertFunnel,
│   │                                       IncidentCard, AgentStrip, EvidenceDrawer,
│   │                                       PlaybookCard, ApprovalModal, PredictionBanner
│   ├── components/extras/          M4      ReasoningPanel, Stopwatch, CostTicker, PostmortemView
│   └── lib/voice.ts  sounds.ts     M4
├── k8s/                            M2      kind config, postgres + memory-hog manifests
└── demo/                           M2, M4  smoke.py (M2), checklist.md and rehearsal-log.md (M4)
```

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
| `DEMO_MODE` | `auto` (live, cache on failure), `cache`, `live` | Member 3 |
| `AUTONOMY_LEVEL` | `2` | Member 3 |
| `ADAPTER` | `simulator` or `k8s` | Member 2 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | from BotFather and the group | Member 4 |
| `BACKEND_URL` | `http://localhost:8000` | Member 4 (bot) |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | Member 1 |
| `VITE_COST_PER_MINUTE` | a figure you can justify on stage | Member 4 |

## Setup and Git workflow

Everyone should be able to run the full app with `make dev` within the first hour. Member 2 creates the repo and Makefile; the others clone and confirm it runs on their laptop.

**Prerequisites:** Python 3.11+, Node 20+, Git; Docker only on Member 2's laptop (for the kind cluster); Telegram on at least one phone.

```bash
git clone <repo-url> && cd agnitia
cp .env.example .env     # fill in your keys
make setup               # pip install -r backend/requirements.txt && npm install --prefix frontend
make dev                 # backend on :8000 with reload + frontend on :5173
make test                # pytest backend/tests
make reset               # everything back to green
make demo                # DEMO_MODE=cache, run only from a frozen tag
```

**Dependencies to install on day one**

- Backend: `fastapi`, `uvicorn[standard]`, `pydantic`, `httpx`, `python-dotenv`, your LLM provider's SDK, `pytest`; later `kubernetes` (Member 2) and `python-telegram-bot` (Member 4)
- Frontend: `react`, `vite`, `typescript`, `tailwindcss`, `@xyflow/react`, `zustand`, `framer-motion`, `recharts`, a React diff-viewer library, `react-markdown`

**Git rules**

1. `main` is the only long-lived branch. Work on short branches named like `m1/alert-funnel` and merge within 1–2 hours.
2. Before merging: `make test` passes, `make dev` starts, and you pressed Inject and Reset once.
3. Open a pull request; your buddy approves within 10 minutes. If they're mid-task, merge it yourself, but only for files you own.
4. Pull from `main` every 30 minutes, and right after any integration window.
5. Shared files (`CONTRACT.md`, `models.py`, `package.json`, `requirements.txt`): announce in chat, change, push within 10 minutes.
6. Commit messages start with your member number: `[M3] add citation verifier`.
7. `.env` is in `.gitignore` from minute one. No API key ever goes into Git.
8. Member 2 creates the tags `cp1`, `cp2` and `final` after each integration check passes. The demo laptop only ever runs a tag.

## Phase 0–1 tracker (hours 0–5, to Checkpoint 1)

Phase 0 is one hour of setup that makes parallel work possible; phase 1 ends with everything Checkpoint 1 needs on screen. Update the Status column as you go.

### Phase 0 — Setup (hours 0–1)

| ID | Task (files) | Owner | Done when | Est. | Status |
| --- | --- | --- | --- | --- | --- |
| 0.1 | Repo, folders, Makefile, `.env.example`, `.gitignore` | Member 2 | `make dev` starts both servers on every laptop | 30 min | Not started |
| 0.2 | `CONTRACT.md` and `models.py` from battle plan §7 | Member 3 | Models import cleanly; all four have read the contract | 30 min | Not started |
| 0.3 | Frontend scaffold: Vite, React, TS, Tailwind, React Flow, zustand, dark theme | Member 1 | Blank dark app loads on :5173 | 30 min | Not started |
| 0.4 | LLM key and one structured-output test call | Member 3 | Script prints valid root-cause JSON | 30 min | Not started |
| 0.5 | `scenarios/db_oom.json`: \~50 log lines, memory curve, events, exactly 56 alerts | Member 4 | Validates against the scenario format; a count script prints 56 | 60 min | Not started |
| 0.6 | Telegram bot in BotFather, team group, token in `.env` | Member 4 | Bot answers "pong" in the group | 15 min | Not started |

### Phase 1 — Skeleton (hours 1–5)

| ID | Task (files) | Owner | Done when | Est. | Status |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Graph functions plus tests (`graph.py`) | Member 2 | Test: db\_oom gives root postgres, 4 impacted, redis excluded | 1 h | Not started |
| 1.2 | Simulator plays scenario files on a timeline (`adapters/simulator.py`) | Member 2 | Inject db\_oom emits memory ramp, 56 alerts, incident in \~12 s, identical every run | 1.5 h | Not started |
| 1.3 | REST routes, `/ws` event bus, reset (`main.py`, `bus.py`) | Member 2 | A socket client sees events; reset returns all services healthy | 1 h | Not started |
| 1.4 | Mock event stream (`mock/events_db_oom.json`) | Member 4 | Member 1's UI plays a full run with the backend off | 45 min | Done |
| 1.5 | Store, reducer, socket with mock replay (`store.ts`, `ws.ts`) | Member 1 | UI state changes as the mock file replays | 45 min | Not started |
| 1.6 | Dependency map, service node with 4 states, animated edges | Member 1 | Root pulses red, victims amber, redis stays green | 1.5 h | Not started |
| 1.7 | Chaos panel, alert funnel, incident card, Reset button | Member 1 | 56 alert cards collapse into INC-104; Reset clears it | 1.5 h | Not started |
| 1.8 | Diagnose agent: prompt, schema, cache (`diagnose.py`, `prompts/`, `cache/`) | Member 3 | Valid root cause for db\_oom and bad\_config; cached JSON saved for both | 1.5 h | Not started |
| 1.9 | Scripted agent\_step emitter for Checkpoint 1 | Member 3 | Reasoning panel shows 6 investigation steps per run | 45 min | Not started |
| 1.10 | Pipeline stub wired in: incident opens → `run_pipeline` returns cached root cause | Member 3 | incident\_update carries the root cause | 30 min | Not started |
| 1.11 | ReasoningPanel component: terminal style, typing effect, auto-scroll | Member 4 | Renders steps from the mock file and scrolls by itself | 45 min | Done |
| 1.12 | `scenarios/bad_config.json` (payment-service crash loop) | Member 4 | Validates; simulator plays it end to end | 45 min | Not started |
| 1.13 | Checkpoint 1 deck (4 slides) and progress board | Member 4 | Battle plan slides 1–4 plus a Done / Building / Next board | 45 min | Not started |
| 1.14 | Integration: live backend to frontend, tag `cp1` | Member 2 with Member 1 | Inject → Reset → Inject works 3 times in a row on the demo laptop | 30 min | Not started |

## Phase 2 tracker (hours 5–11, to Checkpoint 2)

Phase 2 turns the skeleton into the full loop: live AI diagnosis, an ordered playbook, human approval and healing. Integration starts at hour 10 so Checkpoint 2 runs on a tagged build.

| ID | Task (files) | Owner | Done when | Est. | Status |
| --- | --- | --- | --- | --- | --- |
| 2.1 | Pipeline: triage → diagnose → plan → verify, streaming agent\_step (`pipeline.py`) | Member 3 | A live run emits steps and returns root cause plus playbook | 1.5 h | Not started |
| 2.2 | Planner agent with an order check against `topo_order` (`planner.py`) | Member 3 | Dependencies always restart first, even if the model misorders them | 1 h | Not started |
| 2.3 | Citation verifier plus tests (`citations.py`) | Member 3 | A planted fake log line is flagged and confidence drops by 0.2 | 45 min | Not started |
| 2.4 | Demo-mode fallback: over 4 s or an error → cached answer | Member 3 | With Wi-Fi off, the run still completes | 30 min | Not started |
| 2.5 | Executor: steps in order, waits for each probe, rolls back on failure, audit log (`executor.py`) | Member 2 | Approve → nodes recover one by one; audit log lists every action | 1.5 h | Not started |
| 2.6 | Approve, reject, latest-incident and audit endpoints | Member 2 | UI and bot approve through the same endpoint | 30 min | Not started |
| 2.7 | Blast-radius endpoint | Member 2 | Asking about redis returns auth-service, api-gateway, web-ui | 20 min | Not started |
| 2.8 | Smoke test `demo/smoke.py`: inject, wait, approve, assert resolved | Member 2 | Passes 3 runs in a row in under 60 s each | 30 min | Not started |
| 2.9 | kind cluster: postgres with a 64Mi limit plus a memory hog (`k8s/`) | Member 2 | `kubectl` shows postgres OOMKilled after the hog starts | 1.5 h | Not started |
| 2.10 | Evidence drawer: highlighted log lines, memory chart, Verified badges | Member 1 | Opens from the incident card; the cited line is highlighted | 2 h | Not started |
| 2.11 | Playbook card and approval modal with config diff | Member 1 | Diff shows 64Mi → 256Mi; Authorize calls the approve endpoint | 1.5 h | Not started |
| 2.12 | Healing animation, agent strip, mount Member 4's components | Member 1 | Nodes go green in playbook order; agent chips light in sequence | 1 h | Not started |
| 2.13 | Stopwatch and cost ticker (`components/extras/`) | Member 4 | Starts at the first alert, freezes at resolved, clears on Reset | 45 min | Not started |
| 2.14 | Telegram approval bot (`bot/telegram_bot.py`), prompt in battle plan §9 | Member 4 | Tapping Approve on a phone heals the system on screen | 2 h | Not started |
| 2.15 | `cpu_spike.json` and `slow_leak.json` (memory climbs over \~4 minutes) | Member 4 | Both validate and play end to end | 1 h | Not started |
| 2.16 | Checkpoint 2 slides (agent pipeline, safety) and progress board update | Member 4 | Battle plan slides 6–8 drafted | 30 min | Not started |
| 2.17 | Integration, tag `cp2` | Member 2 with all | Smoke test plus a manual full run pass 3 times; phone approval works | 1 h | Not started |

## Phase 3 tracker (hours 11–15, wow layer)

Phase 3 adds the features that make the final memorable, in order of value. Tasks marked stretch are the first to drop if anything runs late; feature freeze is hour 15, no exceptions.

| ID | Task (files) | Owner | Done when | Est. | Status |
| --- | --- | --- | --- | --- | --- |
| 3.1 | Crash predictor and prediction events (`predictor.py`) | Member 2 | slow\_leak shows a countdown at least 60 s before the crash | 1 h | Not started |
| 3.2 | Real-Kubernetes adapter with the `ADAPTER` toggle (`adapters/k8s.py`) | Member 2 | The out-of-memory scenario runs end to end on kind from the same UI | 2.5 h | Not started |
| 3.3 | Autonomy rules, levels 1–3, plus `POST /api/autonomy` (`autonomy.py`) | Member 3 | At level 3 the bad\_config restart runs without approval; the memory patch still asks | 1 h | Not started |
| 3.4 | Postmortem writer and endpoint (`postmortem.py`) | Member 3 | Under 400 words, only facts from the incident JSON | 1 h | Not started |
| 3.5 | Incident memory matching (`memory.py`) | Member 3 | db\_oom shows "matches INC-087" with a similarity score | 1 h | Not started |
| 3.6 | MCP server, stretch (`mcp_server.py`) | Member 3 | Claude Desktop lists open incidents from Agnitia | 1 h | Not started |
| 3.7 | Prediction banner, what-if click mode, autonomy slider | Member 1 | Clicking redis highlights its blast radius; the slider changes the autonomy level | 2 h | Not started |
| 3.8 | Visual polish and projector check | Member 1 | Readable at 1920×1080 from 3 metres; no panel text under 16 px | 1.5 h | Not started |
| 3.9 | Past incidents data, 5 incidents including INC-087 (`past_incidents.json`) | Member 4 | Member 3's matcher loads it without errors | 30 min | Not started |
| 3.10 | Voice briefing and sounds (`lib/voice.ts`, `lib/sounds.ts`) | Member 4 | Summary is read aloud at awaiting\_approval; siren on inject; mute works | 45 min | Not started |
| 3.11 | Postmortem view: render and download (`PostmortemView`) | Member 4 | Button opens the rendered postmortem and downloads a `.md` | 1 h | Not started |
| 3.12 | Final deck, 12 slides, screenshots from the `cp2` build | Member 4 | Every slide passes the zero-context test: a non-engineer can explain it back | 1.5 h | Not started |
| 3.13 | Refresh cached AI answers from the final prompts | Member 3 | Cache regenerated for all 4 scenarios | 20 min | Not started |

## Phase 4 tracker (hours 15–17.5, harden)

No new features after hour 15: phase 4 is only about making the tagged build survive the stage. Every bug found in rehearsal goes to the owner of that file.

| ID | Task (files) | Owner | Done when | Est. | Status |
| --- | --- | --- | --- | --- | --- |
| 4.1 | Feature freeze: merge everything, tag `final` | Member 2 | Tag exists and the smoke test passes on it | 15 min | Not started |
| 4.2 | Demo checklist: every click in the final script with its expected result (`demo/checklist.md`) | Member 4 | Speaker and Driver can follow it without asking questions | 30 min | Not started |
| 4.3 | 10 timed rehearsals, every failure logged (`demo/rehearsal-log.md`) | Member 4 | 10 runs logged with duration and any failure | 1.5 h | Not started |
| 4.4 | Fix bugs from the rehearsal log | Each file's owner | No step fails twice in a row | Ongoing | Not started |
| 4.5 | Second laptop on the same tag with `DEMO_MODE=cache` | Member 2 | A full run works with Wi-Fi off | 30 min | Not started |
| 4.6 | Backup video: full demo plus real-K8s clip, copied to USB and a phone | Member 4, Member 1 driving | Plays from both devices | 30 min | Not started |
| 4.7 | Q&A drill from battle plan §14 | Member 3 runs it, all answer | Every member answers 3 questions in one breath | 20 min | Not started |
| 4.8 | Warm-up step in `make demo`: one AI call before going on stage | Member 3 | `make demo` prints a successful warm-up call | 15 min | Not started |

## Working rhythm

Short, fixed check-ins keep four parallel lanes from drifting apart without eating coding time.

- **Standups every 2 hours** (hours 2, 4, 6, 8, 12, 14), 5 minutes, standing: each member says done, next, blocked, and updates the Status column.
- **Integration windows** at hours 4.5–5, 10–11 and 14.5–15: feature work stops, everyone merges, Member 2 runs the smoke test and tags the build.
- **Handoff pairing:** at each handoff in the diagram above, the giver and the receiver sit together for 10 minutes to plug it in, instead of messaging back and forth.
- **Blocker rule:** stuck for 20 minutes → ask your buddy; stuck for 40 → tell the team and simplify or cut the task using the cut list.
- **The task row is your prompt:** paste `CONTRACT.md`, the relevant interface from this plan, and the task's ID, files and "Done when" into your AI session. That's a complete spec.
- **Breaks:** staggered 45-minute naps between hours 12 and 15, never two members asleep at once, and never during an integration window.

**Definition of done (every task)**

1. Passes its "Done when" check.
2. Works from a fresh `make dev` and again after Reset.
3. No errors in the browser console or backend log.
4. Merged to `main`, and the buddy has seen it.
5. Status set to Done.

## Cut list if the team falls behind

If a phase runs more than an hour late, cut from the top of this list, in order, and tell the team which item went. Each cut has a fallback so the story on stage stays whole.

1. **3.6 MCP server** → mention it as a roadmap item on the architecture slide.
2. **3.5 Incident memory** → drop the on-screen match; keep "learns from past incidents" as roadmap.
3. **3.7 What-if mode and autonomy slider** → keep only the prediction banner.
4. **3.2 Real-Kubernetes adapter in the UI** → show the terminal clip from task 2.9 as a recorded video.
5. **3.11 Postmortem view styling** → open the generated markdown in a plain modal.
6. **3.1 Crash predictor** → end the demo at the postmortem instead of the slow-leak beat.
7. **2.14 Telegram bot** → approve on screen; describe phone approval as the next step.
8. **2.9 kind cluster** → say plainly that the demo runs on the simulator and real clusters are next.

**Never cut:** the dependency map, chaos panel, alert funnel, evidence drawer, ordered playbook, approval with diff, healing animation, Reset button, demo-mode cache and tagged builds. Without these there is no demo.
