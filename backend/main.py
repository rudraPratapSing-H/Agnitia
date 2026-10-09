"""Agnitia Backend - FastAPI Application and Event Stream Routes (Member 2, TASK 1.3)."""

import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.bus import bus, emit
import backend.graph as graph
from backend.models import Alert, Incident, MetricPoint, TimelineEntry
from backend.predictor import seconds_to_limit

# Load environment variables
load_dotenv()

logger = logging.getLogger("agnitia")

app = FastAPI(title="Agnitia API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Module State ─────────────────────────────────────────────────────────────
INCIDENTS: Dict[str, Incident] = {}
LATEST_ID: Optional[str] = None
background_tasks: Set[asyncio.Task] = set()

# Metric buffer per service: deque(maxlen=20) for crash prediction
METRIC_HISTORY: Dict[str, deque] = {}
LAST_PREDICTION_TS: Dict[str, float] = {}

# Valid chaos scenarios per PRD
VALID_SCENARIOS: Set[str] = {"db_oom", "bad_config", "cpu_spike", "slow_leak"}

# Adapter selection via env ADAPTER (default "simulator")
ADAPTER_TYPE = os.getenv("ADAPTER", "simulator")
adapter = None

if ADAPTER_TYPE == "simulator":
    try:
        from backend.adapters.simulator import SimulatorAdapter
        adapter = SimulatorAdapter()
    except ImportError as exc:
        logger.error("SimulatorAdapter import failed: %s", exc)
        adapter = None
elif ADAPTER_TYPE == "k8s":
    try:
        from backend.adapters.k8s import K8sAdapter
        adapter = K8sAdapter()
    except (ImportError, Exception) as exc:
        logger.error("K8sAdapter selected but backend.adapters.k8s could not be imported: %s", exc)
        adapter = None
else:
    logger.error("Unknown ADAPTER type: %s", ADAPTER_TYPE)


# ── Incident Hook ────────────────────────────────────────────────────────────
async def _on_alerts_complete(scenario_id: str, alerts: List[Alert]) -> None:
    """Invoked when the simulator completes emitting scenario alerts."""
    global LATEST_ID
    if not alerts:
        return

    alerting = {a.service for a in alerts}
    try:
        root = graph.find_root(alerting)
        imp = graph.impacted(root, alerting)
    except Exception as exc:
        logger.error("Graph correlation failed for alerting set %s: %s", alerting, exc)
        root = alerts[0].service
        imp = []

    incident_id = alerts[0].incident_id or f"INC-{getattr(adapter, '_incident_counter', 104)}"
    first_ts = alerts[0].ts
    last_ts = alerts[-1].ts

    try:
        dt1 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        delta_s = round(abs((dt2 - dt1).total_seconds()), 1)
    except Exception:
        delta_s = 1.0

    incident = Incident(
        id=incident_id,
        status="analyzing",
        scenario=scenario_id,
        root_service=root,
        impacted_services=imp,
        raw_alert_count=len(alerts),
        started_at=first_ts,
        resolved_at=None,
        rca=None,
        playbook=None,
        timeline=[
            TimelineEntry(t_s=0.0, event="First alert received"),
            TimelineEntry(t_s=delta_s, event=f"Alerts correlated into {incident_id} (root: {root})"),
        ],
    )

    INCIDENTS[incident_id] = incident
    LATEST_ID = incident_id
    await emit("incident_update", incident.model_dump(mode="json"))

    # Attempt to run pipeline from backend.agents.pipeline
    run_pipeline = None
    try:
        from backend.agents.pipeline import run_pipeline as imported_pipeline
        run_pipeline = imported_pipeline
    except (ImportError, AttributeError):
        run_pipeline = None

    if run_pipeline is not None:
        try:
            incident = await run_pipeline(incident, adapter)
        except Exception as exc:
            logger.error("Agent pipeline raised exception: %s", exc)
            incident.status = "analyzing"
            await emit("agent_step", {
                "agent": "pipeline",
                "text": f"Pipeline execution failed: {exc}",
                "status": "failed",
            })
    else:
        logger.warning("backend.agents.pipeline not available; using local stub setting status awaiting_approval.")
        incident.status = "awaiting_approval"

    INCIDENTS[incident_id] = incident
    await emit("incident_update", incident.model_dump(mode="json"))


if adapter is not None:
    adapter.on_alerts_complete = _on_alerts_complete


# ── Predictor & Metrics Listener ─────────────────────────────────────────────
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
        if adapter is not None:
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
            if not INCIDENTS:
                preventive_incident = Incident(
                    id="INC-104",
                    status="awaiting_approval",
                    scenario="slow_leak",
                    root_service=svc,
                    impacted_services=[],
                    raw_alert_count=0,
                    started_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    resolved_at=None,
                    rca=None,
                    playbook=None,
                    timeline=[
                        TimelineEntry(
                            t_s=0.0,
                            event=f"Preventive incident opened: {svc} memory trend projects OOM in {round(sec, 1)}s",
                        ),
                    ],
                )
                INCIDENTS[preventive_incident.id] = preventive_incident
                global LATEST_ID
                LATEST_ID = preventive_incident.id
                await emit("incident_update", preventive_incident.model_dump(mode="json"))


async def _bus_event_listener(envelope: Dict[str, Any]) -> None:
    event_type = envelope.get("type")
    if event_type == "metric_point":
        await _handle_metric_point(envelope.get("payload", {}))
    elif event_type == "reset":
        METRIC_HISTORY.clear()
        LAST_PREDICTION_TS.clear()

bus.add_listener(_bus_event_listener)



# ── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"ok": True}


@app.post("/api/chaos/{scenario}")
async def inject_chaos(scenario: str):
    """Injects a chaos scenario (db_oom | bad_config | cpu_spike | slow_leak)."""
    if scenario not in VALID_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{scenario}'")

    if adapter is None:
        raise HTTPException(status_code=500, detail="Cluster adapter is not initialized")

    try:
        await adapter.inject(scenario)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if hasattr(adapter, "_running_tasks"):
        for t in adapter._running_tasks:
            background_tasks.add(t)

    return {"ok": True, "scenario": scenario}


@app.post("/api/reset")
async def reset_cluster():
    """Restores cluster to healthy state, cancels tasks, and resets incidents."""
    global LATEST_ID

    # Cancel all background tasks
    for task in list(background_tasks):
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    background_tasks.clear()

    if adapter is not None:
        await adapter.reset()

    INCIDENTS.clear()
    LATEST_ID = None

    # Clear predictions on reset: emit prediction {service, seconds: None}
    services_to_clear = set(LAST_PREDICTION_TS.keys()) | set(METRIC_HISTORY.keys()) | set(graph.DEPENDS_ON.keys())
    for s in services_to_clear:
        await emit("prediction", {"service": s, "seconds": None})
    METRIC_HISTORY.clear()
    LAST_PREDICTION_TS.clear()

    # Emit reset event
    await emit("reset", {})

    # Emit service_update for every service
    if adapter is not None:
        services = await adapter.list_services()
        for svc in services:
            await emit("service_update", svc.model_dump(mode="json"))

    return {"ok": True}


@app.get("/api/incidents/latest")
async def get_latest_incident():
    """Returns the latest Incident or null with status 200."""
    if LATEST_ID and LATEST_ID in INCIDENTS:
        return INCIDENTS[LATEST_ID]
    return None


# ── Placeholders returning 501 ───────────────────────────────────────────────

@app.post("/api/incidents/{id}/approve")
async def approve_incident(id: str):
    raise HTTPException(status_code=501, detail="not implemented yet")


@app.post("/api/incidents/{id}/reject")
async def reject_incident(id: str):
    raise HTTPException(status_code=501, detail="not implemented yet")


@app.get("/api/incidents/{id}/postmortem")
async def get_postmortem(id: str):
    raise HTTPException(status_code=501, detail="not implemented yet")


@app.get("/api/blast-radius/{service}")
async def get_blast_radius(service: str):
    raise HTTPException(status_code=501, detail="not implemented yet")


@app.get("/api/incidents/{id}/audit")
async def get_incident_audit(id: str):
    raise HTTPException(status_code=501, detail="not implemented yet")


# ── TTS Endpoint Mount ───────────────────────────────────────────────────────
try:
    from backend.agents.tts import router as tts_router
    app.include_router(tts_router)
except (ImportError, AttributeError):
    pass


# ── WebSocket Stream ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await bus.connect(websocket)
    try:
        # Send current service statuses on connect
        if adapter is not None:
            services = await adapter.list_services()
            for svc in services:
                now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                await websocket.send_json({
                    "type": "service_update",
                    "ts": now_z,
                    "payload": svc.model_dump(mode="json"),
                })

        # Send latest incident if open
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