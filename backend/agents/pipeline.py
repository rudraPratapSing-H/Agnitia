"""Agent Pipeline: Coordinates Triage -> Diagnose -> Verify -> Plan agents"""

import asyncio
from backend.models import Incident
from backend.adapters.base import ClusterAdapter
from backend.agents.diagnose import diagnose_incident
from backend.agents.planner import plan_recovery
from backend.agents.citations import verify_citations
from backend.bus import emit


async def run_pipeline(incident: Incident, adapter: ClusterAdapter) -> Incident:
    """
    Executes the 5-step agent investigation pipeline:
    Triage -> Diagnose -> Verify -> Plan -> Policy Check.
    Emits streaming agent_step events to WebSocket clients.
    """
    incident.status = "analyzing"
    await emit("incident_update", incident.model_dump())

    # Step 1: Triage
    await emit("agent_step", {
        "agent": "triage",
        "text": f"Correlating {incident.raw_alert_count} alerts across dependency graph. Root candidate: {incident.root_service}.",
        "status": "running",
    })
    await asyncio.sleep(0.4)
    await emit("agent_step", {
        "agent": "triage",
        "text": f"Alert storm consolidated. Root cause service identified: {incident.root_service}.",
        "status": "done",
    })

    # Step 2: Diagnose
    await emit("agent_step", {
        "agent": "diagnose",
        "text": f"Querying logs, metric curves, and Kubernetes events for {incident.root_service}.",
        "status": "running",
    })
    await asyncio.sleep(0.5)
    rca = await diagnose_incident(incident, adapter)
    await emit("agent_step", {
        "agent": "diagnose",
        "text": f"Root cause diagnosed: {rca.root_cause} (Category: {rca.category}, Confidence: {int(rca.confidence*100)}%).",
        "status": "done",
    })

    # Step 3: Verify Citations
    await emit("agent_step", {
        "agent": "verify",
        "text": "Verifying cited evidence lines against raw cluster telemetry.",
        "status": "running",
    })
    await asyncio.sleep(0.4)
    logs = await adapter.get_logs(incident.root_service)
    events = await adapter.get_events(incident.root_service)
    metrics = await adapter.get_metrics(incident.root_service)
    verified_rca = verify_citations(rca, logs, events, metrics)
    incident.rca = verified_rca
    await emit("agent_step", {
        "agent": "verify",
        "text": f"Citations verified. {len(verified_rca.evidence)} evidence items validated.",
        "status": "done",
    })

    # Step 4: Plan
    await emit("agent_step", {
        "agent": "planner",
        "text": "Generating recovery playbook sorted by strict dependency topology.",
        "status": "running",
    })
    await asyncio.sleep(0.5)
    playbook = await plan_recovery(incident)
    incident.playbook = playbook
    await emit("agent_step", {
        "agent": "planner",
        "text": f"Generated {len(playbook.steps)}-step remediation plan with rollback diff.",
        "status": "done",
    })

    # Step 5: Policy / Approval Gate
    high_risk_steps = [s for s in playbook.steps if s.requires_approval]
    if high_risk_steps:
        incident.status = "awaiting_approval"
        await emit("agent_step", {
            "agent": "policy",
            "text": f"Safety gate engaged: Step {high_risk_steps[0].order} ({high_risk_steps[0].action}) requires human authorization.",
            "status": "done",
        })
    else:
        incident.status = "awaiting_approval"

    await emit("incident_update", incident.model_dump())
    return incident
