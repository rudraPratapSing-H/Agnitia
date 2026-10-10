# Agnitia — Predictive Auto-Heal Implementation Plan

Oct 9, 2026 · @33° Tilted

## 1. How this plan works

This turns section 7 of the feasibility analysis into buildable tasks, P0 to P10, starting at hour 11 and merged by the hour-15 feature freeze. It adds a failure predictor (logistic regression) and an autonomous patch to Agnitia without touching the existing reactive pipeline. It replaces task 3.1 (crash predictor) and extends 3.3 (autonomy levels) of the earlier implementation plan.

**Who does what**

| Member | Lane in this feature | Branch |
| --- | --- | --- |
| Member 3 | ML core: features, training, live predictor, policy gate; leads tuning | `m3/ml-core` |
| Member 2 | Training-data generator, autonomous action with rollback, simulator and endpoint changes | `m2/ml-data`, `m2/ml-auto` |
| Member 1 | Probability gauge, auto-heal banner, kill switch and autonomy control | `m1/ml-ui` |
| Member 4 | Mock events for the UI, Telegram messages, the slide with measured numbers | `m4/ml-mock-bot` |

**Tool split (Claude usage is limited):** use Antigravity with Gemini Flash for everything except one task. Each step below has either reference code to paste or a ready prompt for Flash. The single Claude session is P5, the policy gate, because a subtle bug there would let a wrong prediction change production.

**Five ground rules**

1. **Behind a flag.** Everything runs only when `PREDICTIVE_HEAL=on`. With it off the app behaves exactly as before, so the feature cannot break the demo.
2. **The model only outputs a number.** It never touches the cluster; the policy gate and the executor decide and act.
3. **No training on stage.** Commit the trained `model.joblib` (under 1 MB). It needs no internet, so this feature also works with Wi-Fi off.
4. **Pure functions with tests.** Features, policy and the success check take their inputs as arguments, including the time, so tests are fast and exact.
5. **Constants live in one file.** Every tunable number is in `ml/config.py`; nobody hard-codes thresholds elsewhere.

**Make room first: this feature is about 7.5 person-hours of new work.** The existing phase 3 already uses about 15 of the team's 16 hours, so cut these now, before building:

| Cut or shrink | Time freed | What we say instead |
| --- | --- | --- |
| 3.6 MCP server | 1 h | Roadmap slide only |
| 3.5 Incident memory | 1 h | Roadmap slide only |
| 3.2 Real-Kubernetes adapter in the UI | 2.5 h | Play the recorded clip from task 2.9 |
| 3.1 Old crash predictor | 1 h | Replaced by P4 |
| 3.7 What-if click mode | 0.75 h | Keep only the prediction banner, which P7 delivers |

That frees about 6.25 hours. The rest is absorbed by starting P1 and P2, which have no dependencies, in any idle gap before hour 11.

## 2. Build order

Four stages keep everyone busy from the first minute: stage 1 has no dependencies, and every later stage starts the moment its inputs exist.

&#91;embedded content: build order · 11 tasks in 4 stages, one finish line\]

The two integration windows use the debug endpoint first, so the UI, the policy gate and the Telegram bot can all be tested before the model exists. P5, the policy gate, is the only task that uses a Claude session.

## 3. Module map

Every new file sits in `backend/ml/` unless noted, so the feature stays out of everyone else's way. Edits to existing files are small and listed in the last rows.

| File | Owner | Task | Depends on | What it exposes |
| --- | --- | --- | --- | --- |
| `ml/config.py` | Member 3 | P2 | nothing | All tunable constants |
| `ml/features.py` | Member 3 | P2 | config | `extract(points) -> 7 numbers or None` |
| `ml/synth.py` | Member 2 | P1 | config | `generate_run(kind, rng) -> (points, fail_t)` |
| `ml/make_data.py` | Member 2 | P1 | synth, features | `build_dataset(n_runs, seed) -> table`; writes `data.csv` |
| `ml/train.py` | Member 3 | P3 | make\_data | Writes `model.joblib`, `report.json`, `report.md` |
| `ml/predict.py` | Member 3 | P4 | model.joblib, features | `Predictor.ingest(metric_point) -> probability or None` |
| `ml/policy.py` | Member 3 | P5 | config | `observe`, `decide`, `record_action`, `PolicyState` |
| `ml/auto.py` | Member 2 | P6 | policy, executor, adapter | `maybe_heal(...)`, `propose_action(...)` |
| `tests/test_features.py`, `test_synth.py`, `test_policy.py`, `test_predict.py`, `test_auto.py` | Owner of the file under test | P2–P6 | the module | Pytest checks |
| `backend/bus.py` (edit, about 8 lines) | Member 2 | P4 | nothing | `subscribe(fn)` |
| `backend/main.py` (edit) | Member 2 | P6 | auto, predict | Hook, kill switch, autonomy, audit and status endpoints |
| `backend/adapters/simulator.py` (edit) | Member 2 | P6 | synth | New metric fields, in-place limit patch, 3 scenarios |
| `backend/models.py` (edit) | Member 2 | P6 | nothing | `Prediction`, `AuditEntry` |
| `frontend/src/store.ts` (edit), `components/PredictionGauge.tsx`, `AutoHealBanner.tsx`, `KillSwitch.tsx` | Member 1 | P7 | the events in section 4 | Gauge, banner, controls |
| `frontend/src/mock/events_slow_leak.json` | Member 4 | P0 | nothing | Mock stream for the UI |
| `bot/telegram_bot.py` (edit) | Member 4 | P8 | audit endpoint | After-the-fact messages |

`ml/data.csv` is generated and git-ignored. `ml/model.joblib`, `ml/report.json` and `ml/report.md` are committed so the demo laptop never retrains.

## 4. Contracts

Agree these before writing code. They extend `CONTRACT.md`; add them to it in the first 15 minutes.

**`ml/config.py` — every tunable in one place (Member 3 creates it first)**

```python
WINDOW_S = 30            # seconds of history per prediction
STEP_S = 0.5             # metric cadence
HORIZON_S = 90           # label: the service fails within this many seconds
THRESHOLD = 0.85         # final value comes from P10 (train.py suggests one)
PERSISTENCE = 5          # consecutive 1-second predictions above the threshold
SUCCESS_P = 0.5          # after a patch: probability must fall below this ...
SAFE_TTL_S = 300         # ... or time-to-limit must exceed this
VERIFY_TIMEOUT_S = 30
HOLD_AFTER_ACTION_S = 60 # no new prediction-driven action on that service
DEMO_SEED = 0            # chosen in P10 so the demo leak behaves the same every run
FEATURES = ["mem_ratio", "mem_slope", "mem_accel", "cpu_ratio",
            "restarts", "err_delta", "volatility"]
```

**`metric_point` event payload (existing event, three new fields — Member 2 adds them to the simulator)**

```jsonc
{ "service": "postgres", "t_s": 41.5, "mem_mb": 52.3, "mem_limit_mb": 64,
  "cpu_pct": 38.0, "restarts": 0, "err_pct": 0.4 }
```

**New WebSocket events**

```jsonc
{ "type": "prediction",   "payload": { "service": "postgres", "probability": 0.91, "threshold": 0.85,
                                      "streak": 4, "seconds_to_limit": 71 } }
{ "type": "healed_auto",  "payload": { "phase": "applied",   // applied | verified | rolled_back
                                      "id": "AUTO-003", "service": "postgres",
                                      "action": "patch_memory_limit",
                                      "params": { "from_mb": 64, "to_mb": 128 },
                                      "probability": 0.93, "policy": "auto-v1" } }
                          // verified adds "result": "healthy"; rolled_back adds "reason"
{ "type": "auto_blocked", "payload": { "service": "postgres", "probability": 0.90,
                                      "reasons": ["R6 cooldown active"] } }
```

**New endpoints**

| Method | Path | Body or query | Returns |
| --- | --- | --- | --- |
| POST | `/api/killswitch` | `{ "on": true }` | `{ "kill_switch": true }` |
| POST | `/api/autonomy` | `{ "level": 1 }` to `3` | `{ "level": 3 }` |
| GET | `/api/audit` | `?since=AUTO-002` | Audit entries after that id |
| GET | `/api/ml/status` | none | `{ "enabled": true, "threshold": 0.85, "model_loaded": true, "kill_switch": false, "level": 3 }` |
| POST | `/api/debug/prediction` | `{ "service": "postgres", "p": 0.95 }`, only when `DEBUG=1` | Feeds a fake probability so the gate, the executor and the UI can be tested before the real model exists |

**New Python models (`backend/models.py`)**

```python
class Prediction(BaseModel):
    service: str; probability: float; streak: int; seconds_to_limit: float | None = None

class AuditEntry(BaseModel):
    id: str; ts: str; policy: str = "auto-v1"; service: str; action: str; params: dict
    probability: float; result: str            # healed | rolled_back | blocked
    reasons: list[str] = []
```

**Bus hook (`backend/bus.py`) — lets the predictor listen without touching the simulator**

```python
_listeners = []
def subscribe(fn):                      # fn is async: fn(type, payload)
    _listeners.append(fn)

async def emit(type, payload):
    ...                                 # existing broadcast to sockets
    for fn in _listeners:
        asyncio.create_task(fn(type, payload))
```

**Environment variables (add to `.env.example`)**

| Variable | Value | Meaning |
| --- | --- | --- |
| `PREDICTIVE_HEAL` | `off` (default) or `on` | Master switch for this whole feature |
| `AUTONOMY_LEVEL` | `3` for the auto-heal demo | Existing variable; level 3 allows unapproved patches |
| `DEBUG` | `0` or `1` | Enables `/api/debug/prediction` |

## 5. Features and training data (P2, P1)

The model's quality depends far more on these two steps than on the model itself, so they get the most detail. P2 is written first because P1 calls it.

### P2 — Feature extraction (Member 3, 45 min, Gemini Flash)

Paste this reference into `ml/features.py`, then ask Flash for the test.

```python
import numpy as np
from .config import WINDOW_S, STEP_S

MIN_POINTS = int(WINDOW_S / STEP_S * 0.75)      # 45 of the 60 points in a full window

def _slope(t, y):
    return float(np.polyfit(t, y, 1)[0])

def extract(points: list[dict]) -> np.ndarray | None:
    """points: last <= 60 metric points of ONE service, oldest first. Returns 7 numbers or None."""
    if len(points) < MIN_POINTS:
        return None
    t = np.array([p["t_s"] for p in points], float); t = t - t[0]
    mem = np.array([p["mem_mb"] / p["mem_limit_mb"] for p in points])   # share of the limit, 0..1
    cpu = np.array([p["cpu_pct"] / 100 for p in points])
    err = np.array([p.get("err_pct", 0.0) for p in points])
    half, n10 = len(points) // 2, int(10 / STEP_S)
    resid = mem - np.polyval(np.polyfit(t, mem, 1), t)
    return np.array([
        mem[-1],                                                         # mem_ratio
        _slope(t, mem) * 100,                                            # mem_slope: % of limit per second
        (_slope(t[half:], mem[half:]) - _slope(t[:half], mem[:half])) * 100,  # mem_accel
        cpu[-1],                                                         # cpu_ratio
        points[-1].get("restarts", 0) - points[0].get("restarts", 0),    # restarts in the window
        err[-n10:].mean() - err[:n10].mean(),                            # err_delta
        float(resid.std()) * 100,                                        # volatility: noise around the trend
    ])
```

The ratio uses each point's own limit, so after an in-place limit patch the ratio drops sharply, which is what lets the probability fall after a fix.

**One deliberate change from the feasibility analysis:** it listed a CPU slope as well; this plan drops it to keep exactly 7 features. Add it back only if saturation failures are caught poorly.

**Test (`tests/test_features.py`)**

1. A perfect leak from 40% to 80% of the limit over 30 s gives `mem_slope` near 1.33 and `mem_accel` and `volatility` near 0.
2. A flat series gives slope near 0.
3. Fewer than 45 points returns `None`.
4. Doubling `mem_limit_mb` on the last point lowers `mem_ratio`.

### P1 — Training data (Member 2, 60 min, Gemini Flash)

`ml/synth.py` generates one fake run of one kind; `ml/make_data.py` slides a 30-second window along it and labels each window.

**Run types** (600 runs in total, seed 7; all points every 0.5 s, memory as a share of a 64 MB limit):

| Kind | Runs | Memory | CPU and errors | `fail_t` (failure time) |
| --- | --- | --- | --- | --- |
| `slow_leak` | 150 (25%) | Starts 35–55%, rises linearly with 1% noise | Normal | The time memory reaches 100%, between 90 and 260 s |
| `fast_leak` | 48 (8%) | Starts 40–60%, reaches 100% in 40–90 s | Normal | When memory reaches 100% |
| `cpu_sat` | 42 (7%) | Flat 40–60% | CPU rises from about 30% to 100% over 60–150 s; `err_pct` climbs to about 20 | When CPU first reaches 100% |
| `healthy` | 210 (35%) | Flat 35–65%, noise 1–3% | CPU 15–50%, noisy | None, 300 s long |
| `spike` | 90 (15%) | Healthy plus one bump of +20–35% for 4–12 s that returns to baseline, peak below 90% | Sometimes a CPU bump of +30–45% | None |
| `sawtooth` | 60 (10%) | Climbs 30% to 75–85% over 40–70 s, drops to 30%, repeats; never reaches the limit | Normal | None |

**Windowing and labels:** for every second `t` from 30 s onward (up to `fail_t` for failing runs), take the last 30 s, compute the 7 features, and label it 1 if `fail_t - t` is at most 90 s, else 0. The dataset columns are `run_id, kind, t_end, fail_t` (blank when none), the 7 features, and `label`.

**Rules that prevent a misleadingly good score**

- Split train and test by `run_id`, never by row; neighbouring windows of one run are near-copies, so a row-wise split leaks the answer.
- Keep the spike and sawtooth runs; they are what teaches the model not to fire on harmless bumps.
- Randomise rates and noise per run; never reuse one curve.

**Prompt for Gemini Flash (P1)**

```text
In backend/ml, write synth.py with generate_run(kind, rng, limit_mb=64.0) -> (points, fail_t), where points
is a list of dicts {t_s, mem_mb, mem_limit_mb, cpu_pct, restarts, err_pct} every 0.5 s and fail_t is a float
or None. Kinds and parameter ranges are in the table below [paste the table]. Then write make_data.py with
build_dataset(n_runs=600, seed=7) that uses a numpy Generator, builds runs in the stated proportions, slides
features.extract (already written) over each run every 1 s, labels windows with HORIZON_S from config.py, and
writes backend/ml/data.csv. Print runs per kind and the share of positive windows. Add test_synth.py checking
that healthy and sawtooth runs never reach 100% memory and that leak runs end at fail_t.
```

**Done when:** `python -m backend.ml.make_data` finishes in under a minute, prints roughly 10–25% positive windows, and the tests pass. Add `make ml` to the Makefile: build the data, then train.

## 6. Training and the live predictor (P3, P4)

### P3 — Train and evaluate (Member 3, 45 min, Gemini Flash)

The numbers that matter are not row-level accuracy but episode results: for each test run, did the alarm fire before the failure, how many seconds ahead, and did healthy runs stay quiet.

```python
# ml/train.py (core; ask Flash to add the report writing and a CLI with --eval-only and --seed)
import joblib, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .config import FEATURES, PERSISTENCE

df = pd.read_csv("backend/ml/data.csv")
tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=7).split(df, groups=df["run_id"]))
train, test = df.iloc[tr].iloc[::3], df.iloc[te].copy()      # every 3rd training window is plenty
model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
model.fit(train[FEATURES], train["label"])
test["p"] = model.predict_proba(test[FEATURES])[:, 1]

def episodes(test, thr):
    """Per run: first time the probability stays >= thr for PERSISTENCE windows in a row."""
    for run_id, g in test.sort_values("t_end").groupby("run_id"):
        streak, alarm = 0, None
        for t, p in zip(g["t_end"], g["p"]):
            streak = streak + 1 if p >= thr else 0
            if streak >= PERSISTENCE:
                alarm = t; break
        yield run_id, g["kind"].iloc[0], alarm, g["fail_t"].iloc[0]   # fail_t is NaN for healthy kinds
```

**What `train.py` must print and save**

1. A threshold sweep from 0.50 to 0.99. For each value: failing test runs caught before `fail_t`, healthy-kind runs that raised a false alarm (by kind), and median warning time in seconds.
2. The suggested threshold: the lowest value whose false-alarm rate on healthy, spike and sawtooth runs is at most 2%.
3. The window-level confusion matrix, precision and recall at that threshold.
4. The coefficient table: each feature and its weight on the standardised scale, sorted by size. This is the "explainable" slide.
5. Files: `model.joblib`, `report.json` (all numbers) and `report.md` (a short readable version for the slide).

**Targets, to be checked rather than assumed:** at least 90% of failing test runs caught before failure, false alarms in at most 2% of healthy-kind runs, and a median warning of at least 40 s. If a number misses, section 10 has the fixes. Because the threshold is picked on the same held-out split, P10 re-checks it on fresh data with a different seed.

**Done when:** `make ml` produces all five outputs, and `model.joblib` is under 1 MB.

### P4 — Live predictor and hook (Member 3 writes `predict.py`, Member 2 adds the hook, 45 min)

```python
# ml/predict.py
import joblib
from collections import defaultdict, deque
from .config import WINDOW_S, STEP_S
from .features import extract

class Predictor:
    def __init__(self, path="backend/ml/model.joblib"):
        self.model = joblib.load(path)
        self.hist = defaultdict(lambda: deque(maxlen=int(WINDOW_S / STEP_S)))
        self.last_scored, self.latest = {}, {}

    def ingest(self, p: dict) -> float | None:
        """Call for every metric_point. Returns a probability about once per second, otherwise None."""
        s = p["service"]
        self.hist[s].append(p)
        if p["t_s"] - self.last_scored.get(s, -1.0) < 1.0:
            return None
        x = extract(list(self.hist[s]))
        if x is None:
            return None
        self.last_scored[s] = p["t_s"]
        self.latest[s] = float(self.model.predict_proba(x.reshape(1, -1))[0, 1])
        return self.latest[s]

    def reset(self):
        self.hist.clear(); self.last_scored.clear(); self.latest.clear()
```

**Hook in `main.py` (Member 2)**

```python
predictor = Predictor() if os.getenv("PREDICTIVE_HEAL") == "on" else None

async def on_bus(type, payload):
    if predictor is None: return
    if type == "reset":
        predictor.reset(); policy_state.reset(); return
    if type != "metric_point": return
    prob = predictor.ingest(payload)
    if prob is None: return
    observe(policy_state, payload["service"], prob)                   # record it for the gate
    streak = streak_of(policy_state, payload["service"])              # consecutive scores above THRESHOLD
    ttl = seconds_to_limit(list(predictor.hist[payload["service"]]), payload["mem_limit_mb"])
    await emit("prediction", {"service": payload["service"], "probability": round(prob, 3),
                              "threshold": THRESHOLD, "streak": streak, "seconds_to_limit": ttl})
    asyncio.create_task(maybe_heal(payload["service"], prob, payload, adapter, policy_state, time.monotonic(), emit, predictor.latest,
                                   lambda s: seconds_to_limit(list(predictor.hist[s]), predictor.hist[s][-1]["mem_limit_mb"])))

bus.subscribe(on_bus)
```

`seconds_to_limit` is the linear-trend helper that already exists from the original crash-predictor task; keep it, because it gives the on-screen countdown and the second half of the success check.

**Tests (`tests/test_predict.py`)**

1. Feed a recorded slow-leak run: the probability rises over time and passes the threshold at least 40 s before `fail_t`.
2. Feed a healthy run and a spike run: the probability never reaches the threshold for 5 seconds in a row.
3. Fewer than 45 points returns `None`; `reset()` empties all state.

## 7. The policy gate (P5)

**Member 3, 60 min, one focused Claude session.** This file decides whether the system may act without a human, so it is pure logic with no I/O and no clock: time is passed in. The reference below is complete; the Claude session's job is to write the tests, run them, and fix any bug without changing the rules.

```python
# ml/policy.py
from collections import deque
from dataclasses import dataclass, field
from .config import THRESHOLD, PERSISTENCE

ALLOW = {"patch_memory_limit", "patch_cpu_limit", "rollout_restart", "scale_replicas"}
STATELESS = {"auth-service", "payment-service", "api-gateway", "web-ui"}
DATA_STORES = {"postgres", "redis"}
LIMIT_ONLY = {"patch_memory_limit", "patch_cpu_limit"}

@dataclass(frozen=True)
class PolicyConfig:
    threshold: float = THRESHOLD
    persistence: int = PERSISTENCE
    max_factor: float = 4.0         # a limit may grow at most 4x in one action
    max_mem_mb: int = 512
    cooldown_s: float = 600
    hourly_cap: int = 5

@dataclass
class PolicyState:
    kill_switch: bool = False
    level: int = 3
    probs: dict = field(default_factory=dict)        # service -> recent probabilities
    last_action: dict = field(default_factory=dict)  # service -> time of last automatic action
    action_times: deque = field(default_factory=deque)
    hold_until: dict = field(default_factory=dict)
    def reset(self):                                 # keeps kill switch and level
        self.probs.clear(); self.last_action.clear(); self.action_times.clear(); self.hold_until.clear()

@dataclass
class Action:
    name: str
    service: str                # one service only, by construction
    params: dict                # memory: {"from_mb", "to_mb"}; cpu: {"from_m", "to_m"}; scale: {"from", "to"}

@dataclass
class Decision:
    allowed: bool
    reasons: list

def observe(state, service, prob, cfg=PolicyConfig()):
    state.probs.setdefault(service, deque(maxlen=cfg.persistence)).append(prob)

def streak_of(state, service, cfg=PolicyConfig()) -> int:
    n = 0
    for p in reversed(state.probs.get(service, ())):
        if p < cfg.threshold: break
        n += 1
    return n

def decide(state, action, now, cfg=PolicyConfig()) -> Decision:
    why, q = [], state.probs.get(action.service, ())
    if state.kill_switch:                  why.append("R7 kill switch is on")
    if state.level < 3:                    why.append("R7 autonomy level is below 3")
    if len(q) < cfg.persistence or min(q) < cfg.threshold:
        why.append("R1/R2 probability not above the threshold for the full persistence window")
    if action.name not in ALLOW:           why.append(f"R3 {action.name} is not on the allow-list")
    if action.name == "rollout_restart" and action.service not in STATELESS:
        why.append("R3 restart is only for stateless services")
    p = action.params
    if action.name == "scale_replicas" and p.get("to", 0) <= p.get("from", 0):
        why.append("R3 scaling down is never automatic")
    if action.name == "patch_memory_limit":
        if p["to_mb"] <= p["from_mb"]:     why.append("R4 a limit change must be an increase")
        if p["to_mb"] > min(p["from_mb"] * cfg.max_factor, cfg.max_mem_mb):
            why.append("R4 above the size cap")
    if action.name == "patch_cpu_limit" and p["to_m"] > p["from_m"] * cfg.max_factor:
        why.append("R4 above the size cap")
    if action.service in DATA_STORES and action.name not in LIMIT_ONLY:
        why.append("R5 data stores only get pure limit increases")
    if now - state.last_action.get(action.service, -1e9) < cfg.cooldown_s: why.append("R6 cooldown active")
    if now < state.hold_until.get(action.service, 0):                      why.append("R6 holding after a recent action")
    if len([t for t in state.action_times if now - t < 3600]) >= cfg.hourly_cap:
        why.append("R6 hourly cap reached")
    return Decision(not why, why)

def record_action(state, service, now, hold_s):
    state.last_action[service] = now
    state.action_times.append(now)
    state.hold_until[service] = now + hold_s
```

The rule numbers match the table in section 5 of the feasibility analysis, and the reasons list names every rule that failed, which is what the audit log and the "policy blocked" message show. `decide` never changes state; only `record_action` does.

**Tests (`tests/test_policy.py`, one focused Claude session)**

1. Below the threshold: blocked with R1/R2. Four of five windows above: blocked. Five of five: allowed.
2. Kill switch on: blocked. Level 2: blocked.
3. `rollout_restart` on `postgres`: blocked (R3 and R5). On `auth-service`: allowed.
4. Memory 64 → 128 and 64 → 256: allowed. 64 → 300: blocked (cap is 4×, so 256). 200 → 512: allowed. 200 → 600: blocked.
5. A decrease or an equal value: blocked. `scale_replicas` from 2 to 1 or 2 to 2: blocked.
6. A second action on the same service 599 s later: blocked; 601 s later: allowed.
7. Five actions on five services within an hour, then a sixth: blocked (hourly cap).
8. A case that breaks two rules lists both reasons.
9. `decide` called twice leaves the state unchanged.

**Prompt for the one Claude session**

```text
I am pasting backend/ml/policy.py. Do not change its rules. Write tests/test_policy.py covering the nine cases
below, run them with pytest, and if a test exposes a bug in policy.py, fix the bug and tell me exactly what
you changed. [paste the nine cases]
```

**Done when:** all nine tests pass and Member 2 can import `decide`, `observe`, `record_action` and `Action` for P6.

## 8. Autonomous action, verify and rollback (P6)

**Member 2, 45 min plus about 45 min of simulator and endpoint edits, Gemini Flash.** When the gate allows an action, `auto.py` applies it, checks that it worked, and either confirms it or undoes it.

```python
# ml/auto.py
import asyncio
from .config import THRESHOLD, SUCCESS_P, SAFE_TTL_S, VERIFY_TIMEOUT_S, HOLD_AFTER_ACTION_S
from . import policy as P
from backend.models import PlaybookStep

AUDIT: list[dict] = []        # if executor.py already keeps an audit list, append to that one instead
_in_flight: set[str] = set()
_last_block: dict[str, float] = {}

def propose_action(service, point) -> P.Action:
    """One reversible fix, chosen from the dominant signal."""
    mem, cpu = point["mem_mb"] / point["mem_limit_mb"], point["cpu_pct"] / 100
    if mem >= cpu:
        lim = int(point["mem_limit_mb"])
        return P.Action("patch_memory_limit", service, {"from_mb": lim, "to_mb": lim * 2})
    if service in P.STATELESS:
        return P.Action("scale_replicas", service, {"from": 1, "to": 2})
    return P.Action("patch_cpu_limit", service, {"from_m": 500, "to_m": 1000})

def inverse(a):
    p = a.params
    if a.name == "patch_memory_limit": return P.Action(a.name, a.service, {"from_mb": p["to_mb"], "to_mb": p["from_mb"]})
    if a.name == "patch_cpu_limit":    return P.Action(a.name, a.service, {"from_m": p["to_m"], "to_m": p["from_m"]})
    if a.name == "scale_replicas":     return P.Action(a.name, a.service, {"from": p["to"], "to": p["from"]})
    return None                                  # a restart cannot be undone

def to_step(a) -> PlaybookStep:
    return PlaybookStep(order=1, service=a.service, action=a.name, params=a.params, risk="medium",
                        requires_approval=False, verify="health check passes")

async def _verified(adapter, service, latest, ttl_of) -> bool:
    for _ in range(VERIFY_TIMEOUT_S):
        await asyncio.sleep(1)
        ttl = ttl_of(service)
        if await adapter.probe(service) and (latest.get(service, 1.0) < SUCCESS_P or (ttl is not None and ttl > SAFE_TTL_S)):
            return True
    return False

async def _try_undo(adapter, action) -> bool:
    inv = inverse(action)
    if inv is None: return False
    if action.name == "patch_memory_limit":      # lowering a limit below current use would kill the service
        cur = (await adapter.get_metrics(action.service))[-1]
        if cur.mem_mb > 0.9 * action.params["from_mb"]: return False
    await adapter.apply_action(to_step(inv))
    return True

async def maybe_heal(service, prob, point, adapter, state, now, emit, latest, ttl_of):
    if prob < THRESHOLD or service in _in_flight:
        return
    action = propose_action(service, point)
    d = P.decide(state, action, now)
    if not d.allowed:
        if now - _last_block.get(service, -1e9) > 30:             # at most one notice per 30 s
            _last_block[service] = now
            await emit("auto_blocked", {"service": service, "probability": round(prob, 3), "reasons": d.reasons})
            _log(service, action, prob, "blocked", d.reasons)
        return
    _in_flight.add(service)
    try:
        base = {"id": f"AUTO-{len(AUDIT) + 1:03d}", "service": service, "action": action.name,
                "params": action.params, "probability": round(prob, 3), "policy": "auto-v1"}
        P.record_action(state, service, now, HOLD_AFTER_ACTION_S)
        await emit("healed_auto", {**base, "phase": "applied"})
        await adapter.apply_action(to_step(action))
        if await _verified(adapter, service, latest, ttl_of):
            await emit("healed_auto", {**base, "phase": "verified", "result": "healthy"})
            _log(service, action, prob, "healed", [], base["id"])
        else:
            undone = await _try_undo(adapter, action)
            why = "health check failed or risk stayed high; " + ("change undone" if undone else "kept the new limit because undoing was unsafe")
            await emit("healed_auto", {**base, "phase": "rolled_back", "reason": why})
            _log(service, action, prob, "rolled_back", [why], base["id"])
    finally:
        _in_flight.discard(service)
```

`_log` builds an `AuditEntry` (timestamp, policy `auto-v1`, service, action, parameters, probability, result, reasons) and appends it to `AUDIT`; ask Flash for it. The rollback skips the gate on purpose, because undoing is the safe direction, but it refuses to lower a memory limit below current use. When it cannot undo, it keeps the new limit and escalates, and the message says so.

**Edits to existing files (Member 2)**

1. **Simulator metric points** carry `mem_limit_mb`, `restarts` and `err_pct`.
2. **`slow_leak`** is generated with `synth.generate_run("slow_leak", np.random.default_rng(DEMO_SEED))`, so the demo matches the training generator; P10 picks `DEMO_SEED` so the would-be failure is at about 100–110 s.
3. **`apply_action` for `patch_memory_limit`** changes the limit in place, with no restart, and the leak keeps climbing at the same rate. The simulator models an in-place resize; on a real cluster a limit change can restart the pod, so say that if asked.
4. **Two new scenarios**, `healthy_spike` and `sawtooth`, built from `synth` with fixed seeds. They must not trigger anything, and running them live is the best answer to "does it over-react?".
5. **`/api/chaos/{scenario}`** accepts the new names.
6. **Endpoints in `main.py`:**

```python
@app.post("/api/killswitch")
async def killswitch(body: dict):
    policy_state.kill_switch = bool(body["on"])
    await emit("agent_step", {"agent": "policy", "status": "done",
                              "text": f"Kill switch {'ON' if policy_state.kill_switch else 'off'}"})
    return {"kill_switch": policy_state.kill_switch}

@app.post("/api/autonomy")
async def autonomy(body: dict):
    policy_state.level = max(1, min(3, int(body["level"])))
    return {"level": policy_state.level}

@app.get("/api/audit")
def audit(since: str = ""):                       # entries after the given id, oldest first
    ids = [e["id"] for e in AUDIT]
    return AUDIT[ids.index(since) + 1:] if since in ids else AUDIT

@app.get("/api/ml/status")
def ml_status():
    return {"enabled": predictor is not None, "threshold": THRESHOLD, "model_loaded": predictor is not None,
            "kill_switch": policy_state.kill_switch, "level": policy_state.level}

@app.post("/api/debug/prediction")                # DEBUG=1 only: test gate, executor and UI without the model
async def debug_prediction(body: dict):
    if os.getenv("DEBUG") != "1": raise HTTPException(404)
    s, p = body["service"], float(body["p"])
    predictor.latest[s] = p; observe(policy_state, s, p)
    await emit("prediction", {"service": s, "probability": p, "threshold": THRESHOLD,
                              "streak": streak_of(policy_state, s), "seconds_to_limit": None})
    point = list(predictor.hist[s])[-1]
    asyncio.create_task(maybe_heal(s, p, point, adapter, policy_state, time.monotonic(), emit, predictor.latest,
                                   lambda s: None))
    return {"ok": True}
```

The debug endpoint is what unblocks Members 1 and 4 before the real model exists: post `p = 0.95` five times and the banner should appear.

**Tests (`tests/test_auto.py`, with a fake adapter and a fake `emit`; patch `asyncio.sleep` so tests run instantly)**

1. Allowed path: events arrive in order `applied`, `verified`; one `healed` audit entry; the cooldown is set.
2. Probe fails and memory is low: change undone, `rolled_back` event, audit entry says so.
3. Probe fails and memory is above 90% of the old limit: not undone, the reason says why.
4. Gate blocks: one `auto_blocked` event, and a second within 30 s is suppressed.
5. Kill switch on: nothing is applied.
6. A second call for the same service while the first is running is ignored.

**Done when:** the six tests pass, and with `DEBUG=1` five posts of `p = 0.95` heal `postgres` in the simulator and a sixth is blocked by the cooldown.

## 9. Mock events, UI, Telegram and the slide (P0, P7, P8, P9)

### P0 — Mock events for the UI (Member 4, 20 min, Gemini Flash)

Member 1 builds the UI against this file, so it comes first. Create `frontend/src/mock/events_slow_leak.json` in the same format as `events_db_oom.json` (a list of `{ "t_ms": ..., "type": ..., "payload": ... }`):

1. About 60 `prediction` events, one per second, with `probability` rising from 0.04 to 0.97 (slowly at first, then steeply), `threshold` 0.85, a `streak` counting from the first value at or above 0.85, and `seconds_to_limit` falling from 160 to 25.
2. At the fifth consecutive value at or above 0.85: a `healed_auto` event with `phase: "applied"` (memory 64 → 128).
3. A `service_update` raising the limit shown on the postgres node to 128.
4. Eight more `prediction` events with the probability falling to 0.2.
5. A `healed_auto` event with `phase: "verified"` and `result: "healthy"`.
6. A second short file, `events_blocked.json`, with one `auto_blocked` event (`reasons: ["R6 cooldown active"]`).

**Done when:** Member 1's replay plays the whole run with the backend off.

### P7 — UI (Member 1, 60 min, Antigravity)

Add to the store (`store.ts`):

```ts
predictions: Record<string, { probability: number; threshold: number; streak: number; secondsToLimit: number | null }>;
autoHeals: Array<{ id: string; service: string; action: string; params: any;
                   phase: 'applied' | 'verified' | 'rolled_back'; probability: number; reason?: string }>;
blocked: { service: string; reasons: string[] } | null;
killSwitch: boolean;
autonomyLevel: 1 | 2 | 3;
```

The reducer handles `prediction`, `healed_auto` (match by `id` and update its `phase`), `auto_blocked` and `reset` (clears all of these).

**Prompt for Antigravity**

```text
Read CONTRACT.md and the section on new events. In the existing React app, add three components and wire them
to the zustand store.
1) PredictionGauge: a horizontal bar from 0 to 1 shown on a service node only when its probability is above 0.2,
   with a tick at the threshold (0.85); green below 0.5, amber 0.5 to 0.85, red above; text "p = 0.91, fails in
   about 70 s" using secondsToLimit when present. Animate changes smoothly.
2) AutoHealBanner: a banner at the top of the incident area for the latest autoHeals entry. applied: "Auto-healing
   postgres: memory 64Mi to 128Mi" with a spinner; verified: green check and "Healthy. Mitigated; root cause
   remains."; rolled_back: red, showing the reason and "A human has been alerted". A second, grey banner for
   blocked: "Policy blocked an automatic fix: <reasons>".
3) KillSwitch: a toggle in the header that POSTs /api/killswitch, plus a 1-2-3 segmented control for autonomy
   level that POSTs /api/autonomy; both read their initial state from GET /api/ml/status.
Text must be at least 16 px for a projector. Test by replaying src/mock/events_slow_leak.json with the backend off.
```

**Done when:** replaying the mock file shows the gauge climbing, the banner moving from applied to verified, and the kill switch posting to the backend (check the network tab).

### P8 — Telegram messages (Member 4, 20 min, Gemini Flash)

The bot already polls the backend. Add a second loop that polls `GET /api/audit?since=<last id>` every 2 s and sends one message per new entry:

```text
Healed:       ✅ Auto-healed postgres
              Predicted failure (p=0.93, about 70 s ahead). Raised memory 64Mi → 128Mi.
              Result: healthy. Mitigated; root cause remains. AUTO-003 · policy auto-v1

Rolled back:  ⚠️ Auto-heal on postgres did not work: <reason>
              A human is needed. AUTO-003

Blocked:      🛑 Policy blocked an automatic fix on postgres: <reasons>
              Needs a human decision. (At most one per service every 5 minutes.)
```

These are information only; the existing approve button flow for incident playbooks is unchanged.

**Done when:** the debug endpoint heals postgres and a Healed message arrives on a phone within 5 seconds.

### P9 — The slide (Member 4, 30 min, Gemini Flash, after the real numbers exist)

Build it from `ml/report.md` after P10 so the numbers are measured. It must pass the zero-context test.

- **Headline:** "Agnitia fixes many problems before they happen."
- **Left:** a screenshot of the gauge climbing and the banner.
- **Right, three numbers from `report.json`:** failing runs caught before failure (x of y); false alarms on healthy runs (n of N); median warning time in seconds.
- **One plain sentence defining the model:** "A simple statistical model turns the last 30 seconds of measurements into a chance of failure."
- **Footnote:** "Measured on held-out simulated runs. Real traces are the next step."
- **Talk-track (20 seconds):** the stage wording from section 5 of the feasibility analysis.

## 10. Tuning and rehearsal (P10)

**Members 3 and 2, 45 min, no AI tool needed.** The goal is a demo that behaves the same way every run: `slow_leak` heals at roughly 40–60 s after injection (the would-be failure is at about 100–110 s), and `healthy_spike` and `sawtooth` never trigger.

**Procedure**

1. Run `make ml` and read `report.json`. Set `THRESHOLD` in `config.py` to the suggested value.
2. Run each scenario five times with `PREDICTIVE_HEAL=on`, `AUTONOMY_LEVEL=3`, pressing Reset between runs. Log the results in `demo/rehearsal-log.md`: time of the heal, the probability when it fired, and whether anything fired on the two harmless scenarios.
3. **Fresh-data check:** generate a second dataset with another seed (`make_data --seed 11 --out data_check.csv`) and evaluate the saved model on it with `train.py --eval-only`. The episode numbers should be within a few points of `report.json`; if they are not, the first score was flattered by the split, so add more variety and retrain.
4. Pick `DEMO_SEED` so `slow_leak` crosses the threshold at about 50 s and would fail at about 105 s. Record the seed in `config.py`.
5. Freeze: commit `model.joblib`, `report.json`, `report.md`, the final `config.py`; tell Member 4 to build the slide from `report.md`.

**Parameters you may change, in this order:** `THRESHOLD`, `PERSISTENCE`, then the leak rate range in `synth.py`, then `HORIZON_S`. Change one at a time and re-run step 2.

**Troubleshooting**

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Probability never reaches the threshold on `slow_leak` | Threshold too high, or the demo leak is outside the training range | Lower `THRESHOLD` by 0.05; check `DEMO_SEED` gives a failure between 90 and 260 s |
| Fires on `healthy_spike` or `sawtooth` | Too few harmless bumps in training, or persistence too short | Raise the spike and sawtooth shares to 20% each and retrain; raise `PERSISTENCE` to 7 |
| Fires too late (under 30 s of warning) | Horizon too short, or threshold too high | Raise `HORIZON_S` to 120 and retrain; lower the threshold |
| Probability falls only slowly after the patch | Window still holds old points | Expected for about 15 s; raise `VERIFY_TIMEOUT_S` to 40 if verification times out |
| Verification fails after a correct patch | `SUCCESS_P` too strict | Raise `SUCCESS_P` to 0.6, or check the simulator really changed the limit |
| Test score is 99%+ | Row-wise split, or label leaked into a feature | Confirm the split uses `run_id`; check features use only past points |
| Heals twice in a row | Cooldown not recorded | Check `record_action` runs before `apply_action` |
| Demo leak heals, then the node turns red 3 minutes later | The leak continues at the same rate; the patch mitigates, it does not fix | Do not linger after the heal; say "mitigated, root cause remains" and move on |

**Done when:** five consecutive `slow_leak` runs heal inside the 40–60 s window, and ten runs of the two harmless scenarios produce no auto action.

## 11. Test plan and acceptance

Tests run in three layers: fast unit tests on every merge, a whole-system smoke test at each integration window, and a manual stage rehearsal.

| Layer | Check | Command or action | Passes when |
| --- | --- | --- | --- |
| Unit | Features on known curves | `pytest tests/test_features.py` | Slope and volatility match hand-computed values |
| Unit | Synthetic runs | `pytest tests/test_synth.py` | Healthy and sawtooth never reach the limit; leaks end at `fail_t` |
| Unit | Policy gate | `pytest tests/test_policy.py` | All 9 cases pass |
| Unit | Predictor | `pytest tests/test_predict.py` | Leak: alarm at least 40 s early; healthy and spike: no 5-in-a-row |
| Unit | Auto action | `pytest tests/test_auto.py` | All 6 cases pass, including both rollback paths |
| Model | Episode results | `make ml` | Meets or honestly reports the targets in section 6; fresh-seed check within a few points |
| Integration | Flag off | `PREDICTIVE_HEAL=off` and the existing smoke test | The earlier loop still passes unchanged |
| Integration | Debug route | `DEBUG=1`, five posts of `p=0.95` | Banner, audit entry and Telegram message all appear |
| Integration | Real model, `slow_leak` | Inject and wait | `prediction` events climb; `healed_auto` applied then verified; no failure ever shown |
| Integration | No over-reaction | Inject `healthy_spike`, then `sawtooth` | No `healed_auto` and no `auto_blocked` |
| Integration | Kill switch | Turn on, inject `slow_leak` | One `auto_blocked` with R7; nothing applied |
| Integration | Forced rollback | Make the simulator probe fail once | `rolled_back` event and a Telegram warning |
| Integration | Offline | Wi-Fi off, `DEMO_MODE=cache` | Everything in this feature works; it needs no network |
| Smoke | Extend `demo/smoke.py` | `python demo/smoke.py --predictive` | Injects `slow_leak`, asserts a `verified` event and zero failures; injects `healthy_spike`, asserts nothing fired; 3 runs in a row |
| Stage | Rehearsal | 10 timed runs with the new beat | No step fails twice; heal time within the 40–60 s window |

**Acceptance for the whole feature** (all must hold at the hour-15 freeze):

1. `slow_leak` heals without any click, and the Telegram message arrives.
2. `healthy_spike` and `sawtooth` produce no automatic action.
3. The kill switch and the autonomy control work from the UI.
4. `report.json` exists with measured numbers, and the slide uses them with the "simulated data" label.
5. With the flag off, the previous demo is unchanged.

If any of these fails at the freeze, apply the fallback ladder in section 12 instead of shipping a flaky autonomous demo.

## 12. Timeline, branches and fallbacks

**By lane** (hours of the 18-hour event; each member also keeps their other phase-3 tasks that were not cut)

| Hours | Member 1 | Member 2 | Member 3 | Member 4 |
| --- | --- | --- | --- | --- |
| Idle gaps before 11 | — | P1: start `synth.py` | P2: features | P0: mock events |
| 11–11.75 | P7: gauge and banner on mock events | P1: `synth.py`, `make_data.py` | P2: features and tests | P0 if not done, then 3.9–3.11 |
| 11.75–12.75 | P7: kill switch and autonomy control | P6: `auto.py` against a stub policy | P5: policy gate (one Claude session) | 3.9–3.11 |
| 12.75–13.5 | 3.8 projector polish | P6: simulator edits, endpoints, new scenarios; `test_auto.py` | P3: train and report | 3.12 final deck |
| 13.5–14.25 | 3.8 polish | Hook in `main.py`, `bus.subscribe`; **integration window** with Member 3 | P4: live predictor | P8: Telegram messages |
| 14.25–15 | Check UI on the demo laptop | P10: tune and rehearse | P10: tune, fresh-seed check, freeze | P9: slide from the real numbers |
| 15 | Feature freeze: Member 2 merges and tags `final` |  |  |  |

**Branches and merge order**

1. `m3/ml-core` first merge: `config.py` and `features.py` (everyone imports them).
2. `m2/ml-data`: `synth.py`, `make_data.py`, then `m3/ml-core` merges `train.py` and the model files.
3. `m3/ml-core`: `policy.py` and its tests.
4. `m2/ml-auto`: `auto.py`, simulator and endpoint edits, `bus.py`, `models.py`.
5. `m3/ml-core`: `predict.py`; Member 2 merges the hook in `main.py`.
6. `m1/ml-ui` and `m4/ml-mock-bot` merge as soon as they pass their own checks.

Separate branches per member, merged by pull request into `main` with the buddy check from the original plan. The flag stays `off` in `.env.example` until the hour-14 integration window passes, then flips to `on` for the demo build only.

**Integration windows**

- **Hour 12.75:** Member 2 posts `p=0.95` to the debug endpoint; Member 1 confirms the banner and gauge update on the real stream, and Member 4 confirms the Telegram message. No model needed.
- **Hour 14:** the real model replaces the debug probabilities; everyone runs `slow_leak` three times.
- **Hour 15:** tag `final` only if section 11's acceptance list passes.

**Fallback ladder (use the first one that applies, and tell the team)**

| If this slips | Do this | What we say on stage |
| --- | --- | --- |
| P5 or P6 not solid by 14.25 | Gate still runs but the action becomes a proposal: show the banner "Proposed fix" and send the existing approve button (level 2) | "It predicts and prepares the fix; autonomy is the next step" |
| P3 model misses its targets | Keep the linear-trend countdown from the original task with a fixed threshold; label it a rule-based predictor and do not call it machine learning | "Trend-based prediction today; a learned model is on the roadmap" |
| Simulator edits slip | Use the debug endpoint during the demo with recorded `p` values replaying a real run | Describe it honestly as a replay of recorded predictions |
| UI polish slips | Banner only, no gauge | "Here is the automatic action and who was told" |

Never ship an autonomous demo that fails the acceptance list; a calm fallback beats a flaky claim.

## 13. Task tracker

Update the Status column as you go; Member 4 turns it into the progress board.

| ID | Task | Owner | Tool | Est. | Done when | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Mock events for the UI | Member 4 | Gemini Flash | 20 min | UI replays a full run with the backend off | Not started |
| P1 | Training data: `synth.py`, `make_data.py` | Member 2 | Gemini Flash | 60 min | Dataset builds in under a minute; 10–25% positive windows; tests pass | Not started |
| P2 | Features: `config.py`, `features.py` | Member 3 | Gemini Flash | 45 min | Four feature tests pass | Not started |
| P3 | Train and report: `train.py` | Member 3 | Gemini Flash | 45 min | `model.joblib` under 1 MB; `report.json` and `report.md` written | Not started |
| P4 | Live predictor and hook: `predict.py`, `main.py`, `bus.py` | Member 3 with Member 2 | Gemini Flash | 45 min | `slow_leak` probability climbs at least 40 s before failure | Not started |
| P5 | Policy gate: `policy.py`, tests | Member 3 | Claude, one session | 60 min | All nine policy tests pass | Not started |
| P6 | Auto action, simulator edits, endpoints | Member 2 | Gemini Flash | 90 min | Six auto tests pass; debug route heals postgres | Not started |
| P7 | Gauge, banner, kill switch, autonomy control | Member 1 | Antigravity | 60 min | Mock replay shows the full sequence; kill switch posts to the backend | Not started |
| P8 | Telegram after-the-fact messages | Member 4 | Gemini Flash | 20 min | Healed message arrives within 5 s of a heal | Not started |
| P9 | The slide with measured numbers | Member 4 | Gemini Flash | 30 min | Uses `report.json` numbers and the simulated-data label | Not started |
| P10 | Tune, fresh-seed check, freeze | Members 3 and 2 | None | 45 min | 5 of 5 `slow_leak` heals in the window; 0 of 10 harmless runs fire | Not started |
