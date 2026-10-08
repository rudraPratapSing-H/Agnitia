"""FastAPI Main Application for Agnitia"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.models import Incident, ServiceNode
from backend.bus import bus, emit
from backend.graph import find_root, impacted, blast_radius
from backend.adapters.simulator import SimulatorAdapter
from backend.agents.pipeline import run_pipeline
from backend.agents.autonomy import set_autonomy_level, get_autonomy_level
from backend.agents.postmortem import write_postmortem
from backend.executor import execute, get_audit_log
from backend.predictor import seconds_to_limit

app = FastAPI(title="Agnitia API", version="1.0.0")

# Enable CORS for frontend Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active state
adapter = SimulatorAdapter()
current_incident: Optional[Incident] = None


class AutonomyRequest(BaseModel):
    level: int


class ApprovalRequest(BaseModel):
    approved_by: str = "web-ui"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await bus.connect(websocket)
    try:
        # On connection, send initial state of services and any active incident
        services = await adapter.list_services()
        for svc in services:
            await websocket.send_json({
                "type": "service_update",
                "ts": datetime.now(timezone.utc).isoformat(),
                "payload": svc.model_dump(),
            })

        if current_incident:
            await websocket.send_json({
                "type": "incident_update",
                "ts": datetime.now(timezone.utc).isoformat(),
                "payload": current_incident.model_dump(),
            })

        while True:
            # Keep socket alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        bus.disconnect(websocket)
    except Exception:
        bus.disconnect(websocket)


@app.get("/api/services")
async def list_services():
    return await adapter.list_services()


@app.get("/api/incidents/latest")
async def get_latest_incident():
    return current_incident


@app.get("/api/blast-radius/{service}")
async def get_service_blast_radius(service: str):
    affected = blast_radius(service)
    return {
        "service": service,
        "impacted_services": affected,
        "estimated_users_impacted": len(affected) * 1250,
    }


@app.post("/api/autonomy")
async def update_autonomy(req: AutonomyRequest):
    if req.level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Autonomy level must be 1, 2, or 3")
    set_autonomy_level(req.level)
    return {"status": "ok", "level": get_autonomy_level()}


@app.post("/api/reset")
async def reset_topology():
    global current_incident
    adapter.reset()
    current_incident = None

    await emit("reset", {})

    services = await adapter.list_services()
    for svc in services:
        await emit("service_update", svc.model_dump())

    return {"status": "ok", "message": "All services restored to healthy"}


@app.post("/api/chaos/{scenario}")
async def inject_chaos(scenario: str):
    global current_incident

    scenario_data = adapter.load_scenario(scenario)
    if not scenario_data:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario}' not found")

    # Reset any existing incident
    adapter.reset()
    await emit("reset", {})

    # Start incident
    incident_id = f"INC-{scenario.upper()[:3]}-104"
    alerts = scenario_data.get("alerts", [])
    alerting_services = {a["service"] for a in alerts}

    root_svc = scenario_data.get("root_service") or find_root(alerting_services)
    impacted_svcs = impacted(root_svc, alerting_services)

    current_incident = Incident(
        id=incident_id,
        status="detected",
        scenario=scenario,
        root_service=root_svc,
        impacted_services=impacted_svcs,
        raw_alert_count=len(alerts),
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    # Launch background simulation task
    asyncio.create_task(_run_chaos_simulation(scenario_data, current_incident))

    return {
        "status": "injected",
        "scenario": scenario,
        "incident_id": incident_id,
        "alert_count": len(alerts),
    }


async def _run_chaos_simulation(scenario_data: dict, incident: Incident):
    """Plays out metric curves, alerts, and triggers agent pipeline."""
    metrics_data = scenario_data.get("metrics", {})
    alerts = scenario_data.get("alerts", [])
    root_svc = incident.root_service

    # Stream metrics
    for svc_id, points in metrics_data.items():
        for pt in points:
            await emit("metric_point", {
                "service": svc_id,
                "t_s": pt.get("t_s", 0.0),
                "mem_mb": pt.get("mem_mb", 0.0),
                "cpu_pct": pt.get("cpu_pct", 0.0),
            })
            await asyncio.sleep(0.04)

    # Check for crash prediction on slow_leak
    if incident.scenario == "slow_leak":
        await emit("prediction", {
            "service": "postgres",
            "seconds": 184.0,
            "message": "PostgreSQL memory trending to limit: estimated OOM crash in 3m 04s",
        })

    # Update node statuses
    svc_node = adapter.services.get(root_svc)
    if svc_node:
        svc_node.status = "root_cause"
        await emit("service_update", svc_node.model_dump())

    for imp in incident.impacted_services:
        imp_node = adapter.services.get(imp)
        if imp_node:
            imp_node.status = "impacted"
            await emit("service_update", imp_node.model_dump())

    # Stream alerts
    for a in alerts:
        a["incident_id"] = incident.id
        await emit("alert", a)
        await asyncio.sleep(0.02)

    # Trigger agent investigation pipeline
    await run_pipeline(incident, adapter)


@app.post("/api/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str, req: ApprovalRequest = ApprovalRequest()):
    global current_incident
    if not current_incident or current_incident.id != incident_id:
        raise HTTPException(status_code=404, detail="Incident not found")

    asyncio.create_task(execute(current_incident, adapter, req.approved_by))
    return {"status": "execution_started", "incident_id": incident_id, "approved_by": req.approved_by}


@app.post("/api/incidents/{incident_id}/reject")
async def reject_incident(incident_id: str):
    global current_incident
    if not current_incident or current_incident.id != incident_id:
        raise HTTPException(status_code=404, detail="Incident not found")

    current_incident.status = "detected"
    await emit("incident_update", current_incident.model_dump())
    return {"status": "rejected", "incident_id": incident_id}


@app.get("/api/incidents/{incident_id}/postmortem")
async def get_incident_postmortem(incident_id: str):
    if not current_incident or current_incident.id != incident_id:
        raise HTTPException(status_code=404, detail="Incident not found")

    markdown = await write_postmortem(current_incident)
    return {"incident_id": incident_id, "postmortem": markdown}


@app.get("/api/audit")
async def get_audit():
    return get_audit_log()
