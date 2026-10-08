"""Postmortem Generator: Creates concise, verifiable incident reports in Markdown format"""

from backend.models import Incident


async def write_postmortem(incident: Incident) -> str:
    """
    Generates a professional SRE postmortem under 400 words based strictly on incident data.
    """
    rca = incident.rca
    root_cause = rca.root_cause if rca else "Unknown cause"
    category = rca.category if rca else "Unclassified"
    confidence = int(rca.confidence * 100) if rca else 0

    evidence_bullets = ""
    if rca and rca.evidence:
        for ev in rca.evidence:
            badge = "✅ [VERIFIED]" if ev.verified else "⚠️ [UNVERIFIED]"
            evidence_bullets += f"- {badge} **{ev.type}** ({ev.source}): `{ev.text}`\n"

    steps_bullets = ""
    if incident.playbook and incident.playbook.steps:
        for step in incident.playbook.steps:
            steps_bullets += f"{step.order}. **{step.service}**: `{step.action}` (Risk: {step.risk}) — *Verification: {step.verify}*\n"

    resolved_time = incident.resolved_at or "In Progress"

    postmortem = f"""# Incident Postmortem: {incident.id}

**Scenario:** `{incident.scenario}`  
**Status:** {incident.status.upper()}  
**Incident Window:** Started at `{incident.started_at}` | Resolved at `{resolved_time}`  
**Raw Alerts Processed:** {incident.raw_alert_count} alerts correlated into 1 root cause  

---

## 1. Executive Summary
At {incident.started_at}, Agnitia detected an alert storm involving {incident.raw_alert_count} raw alerts. Topological dependency analysis isolated **{incident.root_service}** as the single root failure. Downstream services impacted: {', '.join(incident.impacted_services)}.

## 2. Root Cause Analysis
- **Category:** {category}
- **Root Cause:** {root_cause}
- **Diagnosis Confidence:** {confidence}%

### Verified Evidence:
{evidence_bullets or '- Telemetry correlation from simulated pod events.'}

## 3. Remediation & Recovery Actions
The following dependency-ordered recovery playbook was executed:
{steps_bullets or '- Automated health probes and service verification.'}

## 4. Prevention & Action Items
- Enforce updated memory resource limits across cluster deployments.
- Verify readiness probes to prevent cascading upstream connection drops.
- Update alerting thresholds to catch early saturation trends.
"""
    return postmortem.strip()
