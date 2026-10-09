"""Postmortem Generator: Creates concise, verifiable incident reports in Markdown format.

TASK 3.4 (Member 3):
- Under 400 words.
- Uses only facts from the incident JSON.
- Generates postmortem with required sections:
  Summary, Impact, Timeline, Root cause, Resolution steps, What went well, Action items.
- Validates that incident IDs, service names, and numbers outside Action items appear in the facts.
- Retries once on validation failure, then falls back to a deterministic template.
- Fallback is also used on timeout or LLM error, ensuring offline functionality.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from backend.agents import llm
from backend.agents.llm import LLMError, LLMTimeout
from backend.models import Incident

logger = logging.getLogger("agnitia.postmortem")
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_system_prompt() -> str:
    prompt_file = PROMPTS_DIR / "postmortem.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    return (
        "Write a blameless postmortem in markdown from this incident JSON: Summary; "
        "Impact (services, duration); Timeline; Root cause with the cited evidence; "
        "Resolution steps; What went well; 3 action items, each with an owner role. "
        "Under 400 words. Use only facts present in the JSON."
    )


def _calc_duration_s(started_at: str | None, resolved_at: str | None) -> float | int | None:
    """Calculates duration in seconds between started_at and resolved_at."""
    if not started_at or not resolved_at:
        return None
    try:
        start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
        delta = (end_dt - start_dt).total_seconds()
        delta = round(delta, 2)
        return int(delta) if delta.is_integer() else delta
    except Exception:
        return None


def _validate_postmortem(text: str, facts: dict[str, Any]) -> bool:
    """Validates that output has <= 400 words, all required sections, and no hallucinations outside Action items."""
    if not text or not isinstance(text, str):
        return False

    clean_text = text.strip()
    words = clean_text.split()
    if len(words) == 0 or len(words) > 400:
        return False

    lower_text = clean_text.lower()
    required_sections = [
        "summary",
        "impact",
        "timeline",
        "root cause",
        "what went well",
        "action item",
    ]
    for sec in required_sections:
        if sec not in lower_text:
            return False

    if "resolution" not in lower_text:
        return False

    # Separate out Action items section
    match = re.search(r'(?i)(?:^|\n)#*\s*action\s+items', clean_text)
    if match:
        body = clean_text[:match.start()]
    else:
        body = clean_text

    facts_str = json.dumps(facts)
    facts_str_lower = facts_str.lower()

    # 1. Incident IDs in body must appear in facts JSON
    incident_ids = re.findall(r'\bINC-\d+\b', body, re.IGNORECASE)
    for inc_id in incident_ids:
        if inc_id.upper() not in facts_str.upper():
            return False

    # 2. Service names in body must appear in facts JSON
    service_tokens = set(re.findall(r'\b[a-zA-Z0-9_-]+-(?:service|gateway|ui)\b', body, re.IGNORECASE))
    for word in re.findall(r'\b[a-zA-Z0-9_-]+\b', body):
        if word.lower() in ("postgres", "redis"):
            service_tokens.add(word)

    for svc in service_tokens:
        if svc.lower() not in facts_str_lower:
            return False

    # Also check pod names (e.g. postgres-0)
    pod_tokens = re.findall(r'\b[a-zA-Z0-9_-]+-\d+\b', body)
    for pod in pod_tokens:
        if pod.upper().startswith("INC-"):
            continue
        if pod.lower() not in facts_str_lower:
            return False

    # 3. Numbers in body must appear in facts JSON
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', body)
    for num in numbers:
        if num not in facts_str:
            return False

    return True


def _fallback_postmortem(incident: Incident, facts: dict[str, Any]) -> str:
    """Builds a deterministic markdown postmortem directly from the incident facts."""
    inc_id = incident.id
    scenario = incident.scenario
    root = incident.root_service
    duration_str = f"{facts['duration_s']}s" if facts.get("duration_s") is not None else "ongoing"
    impacted = ", ".join(incident.impacted_services) if incident.impacted_services else "None"
    impacted_count = facts.get("impacted_count", len(incident.impacted_services))
    started = incident.started_at
    resolved = incident.resolved_at or "unresolved"

    rca = incident.rca
    root_cause = rca.root_cause if rca else "Root cause not determined"
    category = rca.category if rca else "Unknown"

    evidence_lines = []
    if rca and rca.evidence:
        for ev in rca.evidence:
            evidence_lines.append(f"- **{ev.type}** ({ev.source}): {ev.text}")
    evidence_text = "\n".join(evidence_lines) if evidence_lines else "- No cited evidence available"

    timeline_lines = []
    for item in incident.timeline:
        timeline_lines.append(f"- **+{item.t_s}s**: {item.event}")
    timeline_text = "\n".join(timeline_lines) if timeline_lines else "- No timeline events recorded"

    step_lines = []
    if incident.playbook and incident.playbook.steps:
        for s in incident.playbook.steps:
            step_lines.append(f"{s.order}. `{s.service}`: {s.action}")
    steps_text = "\n".join(step_lines) if step_lines else "- No resolution steps recorded"

    return f"""# Incident Postmortem: {inc_id}

## Summary
Incident {inc_id} ({scenario}) started at {started} and was resolved at {resolved}. Root failure occurred on `{root}` with {incident.raw_alert_count} alerts correlated.

## Impact
- **Impacted services ({impacted_count})**: {impacted}
- **Duration**: {duration_str}

## Timeline
{timeline_text}

## Root cause
- **Category**: {category}
- **Explanation**: {root_cause}
- **Evidence**:
{evidence_text}

## Resolution steps
{steps_text}

## What went well
- Automated topology correlation rapidly pinpointed `{root}` as the root cause.
- Automated dependency ordering verified upstream readiness before dependent restarts.

## Action items
1. **Platform engineer**: Tune memory and CPU limits to prevent recurrence.
2. **Site Reliability Engineer**: Update alerting thresholds to detect saturation earlier.
3. **Software engineer**: Implement readiness probes and connection retry backoff.
""".strip()


async def write_postmortem(incident: Incident) -> str:
    """Generates a verifiable incident postmortem under 400 words based on incident data."""
    facts = incident.model_dump(mode="json")
    facts["duration_s"] = _calc_duration_s(incident.started_at, incident.resolved_at)
    facts["impacted_count"] = len(incident.impacted_services)

    system_prompt = _load_system_prompt()

    try:
        raw_text = await llm.call_text(system_prompt, facts, timeout_s=8.0)
        if _validate_postmortem(raw_text, facts):
            return raw_text.strip()

        logger.warning("Postmortem failed initial validation; attempting one retry")
        retry_prompt = (
            f"{system_prompt}\n\n"
            f"IMPORTANT: The previous output failed validation. "
            f"Ensure every section is included, length is under 400 words, "
            f"and only facts, service names, and numbers from the input JSON are used."
        )
        retry_text = await llm.call_text(retry_prompt, facts, timeout_s=8.0)
        if _validate_postmortem(retry_text, facts):
            return retry_text.strip()

        logger.warning("Postmortem validation failed after retry; using fallback template")
        return _fallback_postmortem(incident, facts)

    except (LLMTimeout, LLMError, Exception) as exc:
        logger.warning("Postmortem LLM generation failed (%s); using fallback template", exc)
        return _fallback_postmortem(incident, facts)


# ── REST endpoint: GET /api/incidents/{id}/postmortem (CONTRACT.md) ─────────

router = APIRouter()


@router.get("/api/incidents/{id}/postmortem", response_class=PlainTextResponse)
async def get_postmortem(id: str) -> str:
    # Deferred import: backend.main imports this module's `router` at startup,
    # so importing it back at module load time would be circular.
    from backend.main import INCIDENTS

    incident = INCIDENTS.get(id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    return await write_postmortem(incident)
