"""Playbook Executor: Runs remediation steps in strict topological order with audit log"""

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
from backend.models import Incident, PlaybookStep
from backend.adapters.base import ClusterAdapter
from backend.bus import emit

audit_log: List[Dict[str, Any]] = []


def get_audit_log() -> List[Dict[str, Any]]:
    return audit_log


async def execute(incident: Incident, adapter: ClusterAdapter, approved_by: str) -> Incident:
    """
    Executes playbook steps in sequence, emits playbook_step & service_update events,
    probes health after each step, and records an audit log.
    """
    if not incident.playbook or not incident.playbook.steps:
        return incident

    incident.status = "healing"
    await emit("incident_update", incident.model_dump())

    audit_entry = {
        "incident_id": incident.id,
        "approved_by": approved_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "steps_executed": [],
    }

    # Sort steps by order
    steps = sorted(incident.playbook.steps, key=lambda s: s.order)

    for step in steps:
        await emit("playbook_step", {
            "order": step.order,
            "service": step.service,
            "action": step.action,
            "status": "running",
        })

        # Apply action via adapter
        result = await adapter.apply_action(step)
        await asyncio.sleep(0.5)

        # Probe service health
        probe_ok = await adapter.probe(step.service)

        status_str = "done" if (result.success and probe_ok) else "failed"

        await emit("playbook_step", {
            "order": step.order,
            "service": step.service,
            "action": step.action,
            "status": status_str,
            "message": result.message,
        })

        # Update service node status
        services = await adapter.list_services()
        for svc in services:
            if svc.id == step.service:
                await emit("service_update", svc.model_dump())

        audit_entry["steps_executed"].append({
            "order": step.order,
            "service": step.service,
            "action": step.action,
            "status": status_str,
            "message": result.message,
        })

        if not probe_ok or not result.success:
            # Abort execution if probe fails
            incident.status = "detected"
            await emit("incident_update", incident.model_dump())
            audit_log.append(audit_entry)
            return incident

    # All steps completed successfully
    incident.status = "resolved"
    incident.resolved_at = datetime.now(timezone.utc).isoformat()
    await emit("incident_update", incident.model_dump())

    audit_log.append(audit_entry)
    return incident
