"""FastAPI Main Application for Agnitia."""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
import logging
import os
import sys
from pathlib import Path
import time
from typing import Any, Dict, Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv(override=True)
REPO_ROOT = Path(__file__).resolve().parent.parent

from backend.bus import bus, emit
import backend.executor as executor
import backend.graph as graph
from backend.models import Incident, MetricPoint, ServiceNode, TimelineItem
from backend.predictor import seconds_to_limit

# Policy and Auto imports (PRD Task P6.4)
from backend.ml import policy as P
from backend.ml import auto
from backend.ml.config import THRESHOLD

logger = logging.getLogger(__name__)

# Try to import run_pipeline from Member 3's agents package
try:
    from backend.agents.pipeline import run_pipeline
except ImportError:
    run_pipeline = None

# Valid chaos scenarios per PRD (db_oom, bad_config, cpu_spike, slow_leak, healthy_spike, sawtooth)
VALID_SCENARIOS: Set[str] = {
    "db_oom",
    "bad_config",
    "cpu_spike",
    "slow_leak",
    "healthy_spike",
    "sawtooth",
}

# Policy state: AUTONOMY_LEVEL clamped to 1..3, default 2 (PRD Task P6.4)
def _get_autonomy_level() -> int:
    raw = os.getenv("AUTONOMY_LEVEL", "2")
    try:
        return max(1, min(3, int(raw)))
    except (TypeError, ValueError):
        return 2

policy_state = P.PolicyState(level=_get_autonomy_level())


class _StubPredictor:
    """Stub predictor used when model.joblib is missing and DEBUG=1 (PRD Task P6.4)."""

    def __init__(self) -> None:
        self.hist: Dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
        self.latest: Dict[str, float] = {}

    def ingest(self, p: dict) -> Optional[float]:
        s = p.get("service")
        if s:
            self.hist[s].append(p)
        return None

    def reset(self) -> None:
        self.hist.clear()
        self.latest.clear()


RealPredictor = None
predictor = None


def init_predictor() -> Any:
    """Lazy predictor loader per PRD Task P6.4."""
    global RealPredictor
    RealPredictor = None

    if os.getenv("PREDICTIVE_HEAL") == "on":
        if sys.platform == "win32":
            try:
                os.add_dll_directory(r"C:\Windows\System32")
            except Exception:
                pass
        model_path = Path(__file__).resolve().parent / "ml" / "model.joblib"
        try:
            from backend.ml.predict import Predictor as _LoadedPredictor
            RealPredictor = _LoadedPredictor
            if model_path.exists():
                try:
                    return RealPredictor(str(model_path))
                except Exception as exc:
                    logger.error("Failed to load model from %s: %s", model_path, exc)
                    return None
            elif os.getenv("DEBUG") == "1":
                return _StubPredictor()
            else:
                return None
        except Exception as exc:
            logger.error("Failed to import backend.ml.predict: %s", exc)
            if os.getenv("DEBUG") == "1":
                return _StubPredictor()
            return None
    return None


predictor = init_predictor()

app = FastAPI(title="OpsOracle API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _make_amazon_incident() -> Incident:
    return Incident(
        id="INC-204",
        status="resolved",
        scenario="db_oom",
        root_service="aurora-orders-db",
        impacted_services=[
            "payment-service",
            "order-service",
            "cart-service",
            "sqs-event-bus",
            "api-gateway",
            "shipping-service",
            "notification-service",
            "web-storefront",
            "mobile-bff",
            "cloud-front",
        ],
        raw_alert_count=84,
        started_at="2026-10-09T03:14:07Z",
        resolved_at="2026-10-09T03:14:49Z",
        rca={
            "root_cause": "Amazon Aurora PostgreSQL primary cluster terminated with exit code 137 (OOMKilled) after saturating its 4096Mi memory limit.",
            "category": "OOMKilled",
            "confidence": 0.98,
            "evidence": [
                {"type": "k8s_event", "source": "aurora-orders-db-0", "text": "Reason: OOMKilled, ExitCode: 137, Memory: 4088Mi/4096Mi", "verified": True},
                {"type": "log", "source": "aurora-orders-db-0", "line": 104, "text": "FATAL: out of memory allocating shared buffer cache", "verified": True},
                {"type": "metric", "source": "aurora-orders-db-0", "text": "buffer_pool_saturation peaked at 99.8% capacity", "verified": True},
            ],
            "similar_incident": {"id": "INC-198", "similarity": 0.96},
        },
        playbook={
            "diff": "resources.limits.memory: 4096Mi -> 8192Mi\nresources.requests.memory: 2048Mi -> 4096Mi",
            "steps": [
                {"order": 1, "service": "aurora-orders-db", "action": "patch_memory_limit", "params": {"from": "4096Mi", "to": "8192Mi"}, "risk": "high", "requires_approval": True, "verify": "port 5432 accepting connections"},
                {"order": 2, "service": "aurora-orders-db", "action": "wait_for_ready", "params": {"timeout_s": 30}, "risk": "low", "requires_approval": False, "verify": "readiness probe 200 OK"},
                {"order": 3, "service": "payment-service", "action": "rollout_restart", "risk": "low", "requires_approval": False, "verify": "payment gateway 200 OK"},
                {"order": 4, "service": "order-service", "action": "rollout_restart", "risk": "low", "requires_approval": False, "verify": "order saga active"},
                {"order": 5, "service": "api-gateway", "action": "reset_circuit_breaker", "risk": "low", "requires_approval": False, "verify": "error rate below 0.1%"},
                {"order": 6, "service": "web-storefront", "action": "verify_health", "risk": "low", "requires_approval": False, "verify": "storefront 200 OK"},
            ],
        },
    )


def _load_default_incidents() -> Dict[str, Incident]:
    incidents = {"INC-204": _make_amazon_incident()}
    fixture_path = REPO_ROOT / "backend" / "tests" / "fixtures" / "incident_db_oom_resolved.json"
    if fixture_path.exists():
        try:
            with open(fixture_path, encoding="utf-8") as f:
                incidents["INC-104"] = Incident.model_validate_json(f.read())
        except Exception:
            pass
    return incidents


# ── Module State ─────────────────────────────────────────────────────────────
INCIDENTS: Dict[str, Incident] = _load_default_incidents()
LATEST_ID: Optional[str] = None
BACKGROUND_TASKS: Set[asyncio.Task] = set()

# Metric buffer per service: deque(maxlen=20) for crash prediction
METRIC_HISTORY: Dict[str, deque] = {}
LAST_PREDICTION_TS: Dict[str, float] = {}


async def _execute_pipeline_for_incident(incident: Incident) -> None:
    """Runs the AI pipeline for an incident and emits incident updates."""
    global LATEST_ID
    if run_pipeline is not None:
        try:
            updated_incident = await run_pipeline(incident, adapter)
            if updated_incident.playbook is None:
                try:
                    from backend.agents.planner import plan_recovery
                    updated_incident.playbook = await plan_recovery(updated_incident)
                except Exception:
                    pass
            # Autonomy policy check - take level from policy_state.level (PRD Task P6.4)
            try:
                from backend.agents.autonomy import needs_approval
            except (ImportError, Exception):
                needs_approval = lambda step, lvl: True
            level = policy_state.level

            if (
                updated_incident.playbook is not None
                and updated_incident.playbook.steps
                and not any(needs_approval(step, level) for step in updated_incident.playbook.steps)
            ):
                actor = f"autonomy-level-{level}"
                INCIDENTS[updated_incident.id] = updated_incident
                LATEST_ID = updated_incident.id

                async def _auto_execute(inc_to_run: Incident) -> None:
                    try:
                        resolved_incident = await executor.execute(inc_to_run, adapter, approved_by=actor)
                        INCIDENTS[resolved_incident.id] = resolved_incident
                        global LATEST_ID
                        LATEST_ID = resolved_incident.id
                        await emit("incident_update", resolved_incident)

                        if resolved_incident.status == "resolved":
                            services_to_clear = set(LAST_PREDICTION_TS.keys()) | {resolved_incident.root_service}
                            for s in services_to_clear:
                                await emit("prediction", {"service": s, "seconds": None})
                            LAST_PREDICTION_TS.clear()
                    except Exception as err:
                        logger.exception("Autonomy execution failed: %s", err)

                auto_task = asyncio.create_task(_auto_execute(updated_incident))
                BACKGROUND_TASKS.add(auto_task)
                auto_task.add_done_callback(BACKGROUND_TASKS.discard)
            else:
                if updated_incident.status != "awaiting_approval":
                    updated_incident.status = "awaiting_approval"

                INCIDENTS[updated_incident.id] = updated_incident
                LATEST_ID = updated_incident.id
                await emit("incident_update", updated_incident)
        except Exception as exc:
            logger.exception("Pipeline execution failed: %s", exc)
            incident.status = "analyzing"
            INCIDENTS[incident.id] = incident
            await emit("agent_step", {
                "agent": "pipeline",
                "text": f"Pipeline failed: {exc}",
                "status": "failed",
            })
            await emit("incident_update", incident)
    else:
        logger.warning("backend.agents.pipeline import failed; using local stub")
        incident.status = "awaiting_approval"
        INCIDENTS[incident.id] = incident
        LATEST_ID = incident.id
        await emit("incident_update", incident)


async def on_alerts_complete(scenario_or_alerts: Any, maybe_alerts: Optional[list] = None) -> None:
    """Incident hook assigned to adapter.on_alerts_complete."""
    global LATEST_ID

    curr_task = asyncio.current_task()
    if curr_task is not None:
        BACKGROUND_TASKS.add(curr_task)
        curr_task.add_done_callback(BACKGROUND_TASKS.discard)

    try:
        if maybe_alerts is not None:
            scenario = str(scenario_or_alerts)
            alerts = maybe_alerts
        elif isinstance(scenario_or_alerts, list):
            alerts = scenario_or_alerts
            scenario = (
                getattr(adapter, "_scenario", {}).get("id", "db_oom")
                if getattr(adapter, "_scenario", None)
                else "db_oom"
            )
        else:
            scenario = str(scenario_or_alerts)
            alerts = []

        if not alerts:
            logger.warning("on_alerts_complete called with empty alerts")
            return

        alerting = {a.service for a in alerts}
        root = graph.find_root(alerting)
        imp = graph.impacted(root, alerting)

        incident_id = alerts[0].incident_id or f"INC-{getattr(adapter, '_incident_counter', 104)}"
        first_alert_ts = alerts[0].ts

        try:
            first_dt = datetime.fromisoformat(first_alert_ts.replace("Z", "+00:00"))
            delta_s = (datetime.now(timezone.utc) - first_dt).total_seconds()
        except Exception:
            delta_s = 0.5
        if delta_s < 0.0:
            delta_s = 0.0

        if incident_id in INCIDENTS:
            existing = INCIDENTS[incident_id]
            existing.raw_alert_count = len(alerts)
            existing.root_service = root
            existing.impacted_services = imp
            existing.timeline.append(
                TimelineItem(
                    t_s=round(delta_s, 2),
                    event=f"Alerts correlated into {incident_id} (root: {root})",
                )
            )
            if existing.playbook is None and existing.status in ("detected", "analyzing"):
                await _execute_pipeline_for_incident(existing)
            else:
                INCIDENTS[existing.id] = existing
                LATEST_ID = existing.id
                await emit("incident_update", existing)
        else:
            timeline = [
                TimelineItem(t_s=0.0, event="First alert received"),
                TimelineItem(
                    t_s=round(delta_s, 2),
                    event=f"Alerts correlated into {incident_id} (root: {root})",
                ),
            ]

            incident = Incident(
                id=incident_id,
                status="analyzing",
                scenario=scenario,
                root_service=root,
                impacted_services=imp,
                raw_alert_count=len(alerts),
                started_at=first_alert_ts,
                resolved_at=None,
                rca=None,
                playbook=None,
                timeline=timeline,
            )

            INCIDENTS[incident.id] = incident
            LATEST_ID = incident.id
            await emit("incident_update", incident)
            await _execute_pipeline_for_incident(incident)
    finally:
        if curr_task is not None:
            BACKGROUND_TASKS.discard(curr_task)


async def _handle_metric_point(payload: dict) -> None:
    svc = payload.get("service")
    if not svc:
        return

    t_s = float(payload.get("t_s", 0.0))
    mem_mb = float(payload.get("mem_mb", 0.0))
    cpu_pct = float(payload.get("cpu_pct", 0.0))

    if svc not in METRIC_HISTORY:
        METRIC_HISTORY[svc] = deque(maxlen=20)
    METRIC_HISTORY[svc].append(
        MetricPoint(t_s=t_s, mem_mb=mem_mb, cpu_pct=cpu_pct, service=svc)
    )

    limit_mb = 64.0
    try:
        services = await adapter.list_services()
        for s in services:
            if s.id == svc:
                limit_mb = s.metrics.mem_limit_mb
                break
    except Exception:
        pass

    sec = seconds_to_limit(list(METRIC_HISTORY[svc]), limit_mb)
    if sec is not None and sec < 300.0:
        last_t = LAST_PREDICTION_TS.get(svc)
        if last_t is None or (t_s - last_t >= 1.0):
            LAST_PREDICTION_TS[svc] = t_s
            await emit("prediction", {"service": svc, "seconds": round(sec, 1)})

        scenario_name = getattr(adapter, "_scenario", {}).get("id") if hasattr(adapter, "_scenario") and adapter._scenario else None
        if scenario_name == "slow_leak":
            # The first time it crosses 300 s with no incident open, create a PREVENTIVE incident
            open_incident = any(
                inc.status in ("detected", "analyzing", "awaiting_approval", "healing")
                for inc in INCIDENTS.values()
            )
            if not open_incident:
                incident_id = (
                    getattr(adapter, "_current_incident_id", None)
                    or f"INC-{getattr(adapter, '_incident_counter', 104)}"
                )

                now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                preventive_incident = Incident(
                    id=incident_id,
                    status="analyzing",
                    scenario="slow_leak",
                    root_service=svc,
                    impacted_services=[],
                    raw_alert_count=0,
                    started_at=now_z,
                    resolved_at=None,
                    rca=None,
                    playbook=None,
                    timeline=[
                        TimelineItem(
                            t_s=0.0,
                            event=f"Preventive alert: memory leak detected on {svc} (<300s to limit)",
                        ),
                    ],
                )
                INCIDENTS[preventive_incident.id] = preventive_incident
                global LATEST_ID
                LATEST_ID = preventive_incident.id
                await emit("incident_update", preventive_incident)

                pipe_task = asyncio.create_task(_execute_pipeline_for_incident(preventive_incident))
                BACKGROUND_TASKS.add(pipe_task)
                pipe_task.add_done_callback(BACKGROUND_TASKS.discard)


async def _bus_event_listener(envelope: Dict[str, Any]) -> None:
    event_type = envelope.get("type")
    if event_type == "metric_point":
        await _handle_metric_point(envelope.get("payload", {}))
    elif event_type == "reset":
        METRIC_HISTORY.clear()
        LAST_PREDICTION_TS.clear()

bus.add_listener(_bus_event_listener)


def init_adapter(adapter_type: Optional[str] = None) -> Any:
    """Initializes adapter based on ADAPTER env var or argument."""
    adp_name = adapter_type or os.getenv("ADAPTER", "simulator")
    if adp_name == "simulator":
        from backend.adapters.simulator import SimulatorAdapter
        adp = SimulatorAdapter()
    elif adp_name == "k8s":
        try:
            from backend.adapters.k8s import K8sAdapter
            adp = K8sAdapter()
        except (ImportError, AttributeError) as exc:
            raise RuntimeError(
                f"k8s adapter cannot be loaded: backend.adapters.k8s does not exist or is not implemented yet ({exc})"
            ) from exc
    else:
        raise ValueError(f"Unknown ADAPTER: {adp_name}")

    adp.on_alerts_complete = on_alerts_complete
    return adp


adapter = init_adapter()


# ── Predictive Auto-Heal Bus Hook (PRD Section 6 / P4 / P6.4) ────────────────

async def on_bus(type: str, payload: dict) -> None:
    if type == "reset":
        if predictor is not None:
            predictor.reset()
        policy_state.reset()
        auto.reset_state()
        return

    if predictor is None:
        return
    if type != "metric_point":
        return

    prob = predictor.ingest(payload)
    if prob is None:
        return

    svc = payload.get("service")
    if not svc:
        return

    P.observe(policy_state, svc, prob)
    streak = P.streak_of(policy_state, svc)
    hist_points = list(predictor.hist[svc])
    ttl = seconds_to_limit(hist_points, float(payload.get("mem_limit_mb", 64.0)))

    await emit(
        "prediction",
        {
            "service": svc,
            "probability": round(prob, 3),
            "threshold": THRESHOLD,
            "streak": streak,
            "seconds_to_limit": ttl,
        },
    )

    heal_task = asyncio.create_task(
        auto.maybe_heal(
            svc,
            prob,
            payload,
            adapter,
            policy_state,
            time.monotonic(),
            emit,
            predictor.latest,
            lambda s: seconds_to_limit(
                list(predictor.hist[s]),
                float(predictor.hist[s][-1].get("mem_limit_mb", 64.0))
                if predictor.hist.get(s) and isinstance(predictor.hist[s][-1], dict) and "mem_limit_mb" in predictor.hist[s][-1]
                else 64.0,
            )
            if predictor.hist.get(s)
            else None,
        )
    )
    BACKGROUND_TASKS.add(heal_task)
    heal_task.add_done_callback(BACKGROUND_TASKS.discard)


bus.subscribe(on_bus)


# ── REST Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/chaos/{scenario}")
async def inject_chaos(scenario: str, preset: Optional[str] = None):
    if preset in ("amazon-scale", "amazon") or scenario in ("amazon_db_oom", "aurora_oom"):
        inc = _make_amazon_incident()
        inc.status = "awaiting_approval"
        inc.started_at = datetime.now(timezone.utc).isoformat()
        INCIDENTS[inc.id] = inc
        global LATEST_ID
        LATEST_ID = inc.id
        await emit("incident_update", inc)
        return {"ok": True, "scenario": scenario, "preset": "amazon-scale", "incident_id": inc.id}

    if scenario not in VALID_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{scenario}'")

    if getattr(adapter, "_scenario", None) is not None:
        raise HTTPException(status_code=409, detail="A scenario is already playing")

    try:
        incident_id = await adapter.inject(scenario)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if hasattr(adapter, "_running_tasks"):
        for t in adapter._running_tasks:
            BACKGROUND_TASKS.add(t)

    return {"ok": True, "scenario": scenario}


@app.post("/api/incidents/sync")
async def sync_incident(incident_data: dict):
    global LATEST_ID
    inc_id = incident_data.get("id")
    if not inc_id:
        raise HTTPException(status_code=400, detail="Missing incident id")

    try:
        inc = Incident.model_validate(incident_data)
        INCIDENTS[inc_id] = inc
        LATEST_ID = inc_id
        await emit("incident_update", inc)
        return {"ok": True, "incident": inc_id, "status": inc.status}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/reset")
async def reset():
    global LATEST_ID

    current = asyncio.current_task()
    for task in list(BACKGROUND_TASKS):
        if task is not current and not task.done():
            task.cancel()
    BACKGROUND_TASKS.clear()

    await adapter.reset()
    INCIDENTS.clear()
    LATEST_ID = None
    executor.clear_audit()

    # Clear predictions on reset: emit prediction {service, seconds: None}
    services_to_clear = set(LAST_PREDICTION_TS.keys()) | set(METRIC_HISTORY.keys()) | set(graph.DEPENDS_ON.keys())
    for s in services_to_clear:
        await emit("prediction", {"service": s, "seconds": None})
    METRIC_HISTORY.clear()
    LAST_PREDICTION_TS.clear()

    await emit("reset", {})
    services = await adapter.list_services()
    for svc in services:
        await emit("service_update", svc)

    return {"ok": True}


@app.get("/api/incidents/latest")
async def get_latest_incident():
    if LATEST_ID and LATEST_ID in INCIDENTS:
        return INCIDENTS[LATEST_ID]
    return None


@app.get("/api/health")
async def health():
    return {"status": "ok", "ok": True}


@app.get("/api/services")
async def list_services():
    return await adapter.list_services()


# ── Incident Lifecycle Routes (TASK 2.6) ──────────────────────────────────────

@app.post("/api/incidents/{id}/approve", status_code=202)
async def approve_incident(id: str, body: Optional[dict] = None):
    if id not in INCIDENTS:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    incident = INCIDENTS[id]
    if incident.status != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Incident '{id}' is currently '{incident.status}', not 'awaiting_approval'",
        )

    actor = "ui"
    if body and isinstance(body, dict):
        actor = body.get("approved_by") or body.get("actor") or "ui"

    incident.status = "healing"
    await emit("incident_update", incident)

    async def _execute_and_update(inc: Incident, adp: Any, approved_by_name: str) -> None:
        global LATEST_ID
        curr = asyncio.current_task()
        try:
            if inc.id == "INC-204" or getattr(inc, "root_service", "") == "aurora-orders-db":
                inc.status = "healing"
                await emit("incident_update", inc)
                await asyncio.sleep(1.0)
                inc.status = "resolved"
                inc.resolved_at = datetime.now(timezone.utc).isoformat()
                INCIDENTS[inc.id] = inc
                LATEST_ID = inc.id
                await emit("incident_update", inc)
                return

            resolved_incident = await executor.execute(inc, adp, approved_by_name)
            INCIDENTS[resolved_incident.id] = resolved_incident
            LATEST_ID = resolved_incident.id
            await emit("incident_update", resolved_incident)

            # When the incident resolves, emit prediction {service, seconds: null}
            if resolved_incident.status == "resolved":
                services_to_clear = set(LAST_PREDICTION_TS.keys()) | {resolved_incident.root_service}
                for s in services_to_clear:
                    await emit("prediction", {"service": s, "seconds": None})
                LAST_PREDICTION_TS.clear()
        except asyncio.CancelledError:
            logger.info("Execution task for %s was cancelled", inc.id)
            raise
        except Exception as exc:
            logger.exception("Unexpected error in execution task: %s", exc)
        finally:
            if curr:
                BACKGROUND_TASKS.discard(curr)

    exec_task = asyncio.create_task(_execute_and_update(incident, adapter, actor))
    BACKGROUND_TASKS.add(exec_task)
    exec_task.add_done_callback(BACKGROUND_TASKS.discard)

    return JSONResponse(status_code=202, content={"ok": True, "status": "healing"})


@app.post("/api/incidents/{id}/reject")
async def reject_incident(id: str, body: Optional[dict] = None):
    if id not in INCIDENTS:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    incident = INCIDENTS[id]
    if incident.status != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Incident '{id}' is currently '{incident.status}', not 'awaiting_approval'",
        )

    actor = "ui"
    if body and isinstance(body, dict):
        actor = body.get("rejected_by") or body.get("approved_by") or body.get("actor") or "ui"

    try:
        started = datetime.fromisoformat(incident.started_at.replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        t_s = max(0.0, round((datetime.now(timezone.utc) - started).total_seconds(), 2))
    except Exception:
        t_s = 0.0

    incident.timeline.append(TimelineItem(t_s=t_s, event=f"Playbook rejected by {actor}"))
    incident.status = "detected"
    incident.playbook = None

    await emit("incident_update", incident)
    return {"ok": True}


@app.get("/api/incidents/{id}/audit")
async def get_incident_audit(id: str):
    if id not in INCIDENTS:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")
    return executor.get_audit(id)


# ── Predictive Auto-Heal & Policy Endpoints (PRD Section 4, 6, 8 / P6.4) ──────

@app.post("/api/killswitch")
async def killswitch(body: dict):
    policy_state.kill_switch = bool(body.get("on", False))
    await emit(
        "agent_step",
        {
            "agent": "policy",
            "status": "done",
            "text": f"Kill switch {'ON' if policy_state.kill_switch else 'off'}",
        },
    )
    return {"kill_switch": policy_state.kill_switch}


@app.post("/api/autonomy")
async def autonomy(body: dict):
    policy_state.level = max(1, min(3, int(body.get("level", 2))))
    return {"level": policy_state.level}


@app.get("/api/audit")
def audit(since: str = ""):
    ids = [e["id"] for e in auto.AUDIT]
    return auto.AUDIT[ids.index(since) + 1:] if since in ids else auto.AUDIT


@app.get("/api/ml/status")
def ml_status():
    is_on = os.getenv("PREDICTIVE_HEAL") == "on"
    return {
        "enabled": is_on,
        "threshold": THRESHOLD,
        "model_loaded": bool(
            is_on
            and predictor is not None
            and getattr(type(predictor), "__name__", "") == "Predictor"
            and hasattr(predictor, "model")
        ),
        "kill_switch": policy_state.kill_switch,
        "level": policy_state.level,
    }


@app.post("/api/debug/prediction")
async def debug_prediction(body: dict):
    if os.getenv("DEBUG") != "1":
        raise HTTPException(status_code=404, detail="Debug endpoint disabled")
    if predictor is None:
        raise HTTPException(status_code=409, detail="Predictor is None")

    s = body.get("service")
    if not s:
        raise HTTPException(status_code=400, detail="Missing service")
    p = float(body.get("p", 0.0))

    predictor.latest[s] = p
    P.observe(policy_state, s, p)
    await emit(
        "prediction",
        {
            "service": s,
            "probability": p,
            "threshold": THRESHOLD,
            "streak": P.streak_of(policy_state, s),
            "seconds_to_limit": None,
        },
    )

    if s in predictor.hist and len(predictor.hist[s]) > 0:
        point = list(predictor.hist[s])[-1]
    else:
        services = await adapter.list_services()
        svc_node = next((svc for svc in services if svc.id == s), None)
        if svc_node is not None:
            point = {
                "service": s,
                "t_s": 0.0,
                "mem_mb": svc_node.metrics.mem_mb,
                "mem_limit_mb": svc_node.metrics.mem_limit_mb,
                "cpu_pct": svc_node.metrics.cpu_pct,
                "restarts": svc_node.metrics.restarts,
                "err_pct": 0.0,
            }
        else:
            point = {
                "service": s,
                "t_s": 0.0,
                "mem_mb": 40.0,
                "mem_limit_mb": 64.0,
                "cpu_pct": 12.0,
                "restarts": 0,
                "err_pct": 0.0,
            }

    heal_task = asyncio.create_task(
        auto.maybe_heal(
            s,
            p,
            point,
            adapter,
            policy_state,
            time.monotonic(),
            emit,
            predictor.latest,
            lambda s: None,
        )
    )
    BACKGROUND_TASKS.add(heal_task)
    heal_task.add_done_callback(BACKGROUND_TASKS.discard)

    return {"ok": True}


# Postmortem route: owned by Member 3. Include router if present, fallback to 501.
try:
    from backend.agents.postmortem import router as postmortem_router
    app.include_router(postmortem_router)
except (ImportError, AttributeError):
    @app.get("/api/incidents/{id}/postmortem")
    async def get_postmortem(id: str):
        raise HTTPException(status_code=501, detail="not implemented yet")


# Illustrative simulated percentage of users affected if a service fails (simulated, never measured).
USER_IMPACT_PCT: Dict[str, int] = {
    "postgres": 100,
    "redis": 70,
    "auth-service": 70,
    "payment-service": 40,
    "api-gateway": 100,
    "web-ui": 100,
}


@app.get("/api/blast-radius/{service}")
async def get_blast_radius(service: str):
    if service not in graph.DEPENDS_ON:
        raise HTTPException(status_code=404, detail=f"Service '{service}' not found")
    try:
        affected = graph.blast_radius(service)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Service '{service}' not found")

    return {
        "service": service,
        "affected_services": affected,
        "users_affected_pct": USER_IMPACT_PCT.get(service, 0),
        "note": "illustrative simulator figure",
    }



# Voice briefing: POST /api/tts {text} -> audio/wav (task 3.10, Google/Gemini TTS)
try:
    from backend.agents.tts import router as tts_router
    app.include_router(tts_router)
except (ImportError, AttributeError):
    @app.post("/api/tts")
    async def post_tts():
        raise HTTPException(status_code=501, detail="not implemented yet")


# ── WebSocket Stream ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await bus.connect(websocket)
    try:
        services = await adapter.list_services()
        for svc in services:
            now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            await websocket.send_json({
                "type": "service_update",
                "ts": now_z,
                "payload": svc.model_dump(mode="json"),
            })

        if LATEST_ID and LATEST_ID in INCIDENTS:
            latest_inc = INCIDENTS[LATEST_ID]
            now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            await websocket.send_json({
                "type": "incident_update",
                "ts": now_z,
                "payload": latest_inc.model_dump(mode="json"),
            })

        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception) as exc:
        logger.debug("WebSocket client disconnected: %s", exc)
    finally:
        bus.disconnect(websocket)
