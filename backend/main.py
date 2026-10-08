"""FastAPI Main Application for Agnitia."""

import asyncio
from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from backend.bus import bus, emit
import backend.executor as executor
import backend.graph as graph
from backend.models import Incident, ServiceNode, TimelineItem

logger = logging.getLogger(__name__)

# Try to import run_pipeline from Member 3's agents package
try:
    from backend.agents.pipeline import run_pipeline
except ImportError:
    run_pipeline = None

# Valid chaos scenarios per PRD
VALID_SCENARIOS: Set[str] = {"db_oom", "bad_config", "cpu_spike", "slow_leak"}

app = FastAPI(title="Agnitia API", version="1.0.0")

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

# ── Module State ─────────────────────────────────────────────────────────────
INCIDENTS: Dict[str, Incident] = {}
LATEST_ID: Optional[str] = None
BACKGROUND_TASKS: Set[asyncio.Task] = set()


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

        if run_pipeline is not None:
            try:
                updated_incident = await run_pipeline(incident, adapter)
                if updated_incident.playbook is None:
                    try:
                        from backend.agents.planner import plan_recovery
                        updated_incident.playbook = await plan_recovery(updated_incident)
                    except Exception:
                        pass
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
            logger.warning("backend.agents.pipeline import failed (M3 not merged yet); using local stub")
            incident.status = "awaiting_approval"
            INCIDENTS[incident.id] = incident
            LATEST_ID = incident.id
            await emit("incident_update", incident)
    finally:
        if curr_task is not None:
            BACKGROUND_TASKS.discard(curr_task)


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


# ── REST Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/chaos/{scenario}")
async def inject_chaos(scenario: str):
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
        curr = asyncio.current_task()
        try:
            resolved_incident = await executor.execute(inc, adp, approved_by_name)
            INCIDENTS[resolved_incident.id] = resolved_incident
            global LATEST_ID
            LATEST_ID = resolved_incident.id
            await emit("incident_update", resolved_incident)
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


@app.get("/api/audit")
async def get_audit():
    if LATEST_ID and LATEST_ID in INCIDENTS:
        return executor.get_audit(LATEST_ID)
    return []


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


@app.post("/api/autonomy")
async def update_autonomy():
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
