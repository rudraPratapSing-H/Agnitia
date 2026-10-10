# OpsOracle — Autonomous Incident Remediation Agent

> **One-line pitch:** OpsOracle is an AI on-call engineer. It turns a storm of 50+ alerts into one root cause with verifiable proof, builds a dependency-ordered recovery playbook, and heals the system upon human authorization.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- Node.js 20+
- Git

### 2. Environment Setup
```bash
# Clone and enter repo
git clone https://github.com/rudraPratapSing-H/Agnitia.git
cd Agnitia

# Copy environment variables
cp .env.example .env

# Install dependencies (backend + frontend)
make setup
```

### 3. Run Development Servers
```bash
make dev
```
- Backend runs on `http://localhost:8000` (FastAPI + WebSocket at `/ws`)
- Frontend runs on `http://localhost:5173` (React + Vite)

### 4. Run Tests & Reset
```bash
# Run backend test suite
make test

# Reset topology to all-green state
make reset
```

---

## 🏗️ Architecture & Ownership Map

| Lane | Role | Core Responsibility | Primary Files |
|---|---|---|---|
| **Member 1** | Frontend Lead | Mission-control UI, dependency map, alert storm funnel, approval modal | `frontend/src/*` |
| **Member 2** | Backend & Simulator | FastAPI server, WebSocket event bus, graph correlation, playbook executor | `backend/main.py`, `backend/bus.py`, `backend/graph.py`, `backend/executor.py`, `backend/adapters/*` |
| **Member 3** | AI Agents | Agent pipeline (Triage → Diagnose → Plan → Verify), citation guard, cache | `backend/agents/*`, `backend/models.py`, `CONTRACT.md` |
| **Member 4** | Integrations & Content | Scenario datasets, Telegram approval bot, pitch deck, rehearsal metrics | `backend/scenarios/*`, `bot/telegram_bot.py`, `demo/*` |

---

## 🎬 Demo

- Click-by-click script with expected results: [`demo/checklist.md`](demo/checklist.md).
- Automated end-to-end check (inject → approve → resolved, 3 runs): `python demo/smoke.py --runs 3`.
- Live progress board: open [`demo/progress-board/index.html`](demo/progress-board/index.html) (serve the `demo/progress-board/` folder over HTTP — it `fetch()`es `status.json`, so opening the file directly won't load data).
- Rehearsal timing log: [`demo/rehearsal-log.md`](demo/rehearsal-log.md).
- `make demo` runs `DEMO_MODE=cache` only, from a frozen git tag — the demo laptop never runs a branch.

## ⚡ Chaos Scenarios
OpsOracle includes 4 deterministic chaos scenarios:
1. `db_oom`: PostgreSQL memory limit exceeded (OOMKilled), 56 downstream alerts collapsed into 1 incident.
2. `bad_config`: Payment-service misconfiguration crash loop.
3. `cpu_spike`: CPU throttling inducing high gateway latency.
4. `slow_leak`: Gradual memory leak triggering predictive crash warnings.

---

## 🛡️ Safety & Guardrails
- **Strict Allow-List:** Only non-destructive actions are permitted (`patch_memory_limit`, `rollout_restart`, etc.). Destructive commands are blocked.
- **Topological Ordering:** Fixes execute strictly dependencies-first to prevent secondary crashes.
- **Citation Verifier:** Diagnosis claims cite exact log lines and k8s events; unverifiable claims lower the confidence score.
- **Human Approval Gate:** Risky actions require explicit authorization via the UI or Telegram bot.
