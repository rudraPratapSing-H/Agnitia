"""Agent Pipeline: Coordinates investigation steps and Checkpoint 1 pipeline stub"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from backend.models import Incident, RCA
from backend.adapters.base import ClusterAdapter

try:
    from backend.bus import emit
except ImportError:
    async def emit(type: str, payload: dict):
        print("[emit]", type, payload)

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
CACHE_DIR = Path(__file__).resolve().parent / "cache"


async def emit_scripted_steps(scenario_id: str, incident: Incident) -> None:
    """
    Emits six scripted agent_step events per run spaced ~0.8s apart:
    Two triage steps and four diagnose steps.
    All dynamic values are extracted from the incident and scenario telemetry.
    """
    root_svc = incident.root_service
    scenario_file = SCENARIOS_DIR / f"{scenario_id}.json"
    cache_file = CACHE_DIR / f"{scenario_id}.json"

    scenario_data: Optional[dict] = None
    if scenario_file.exists():
        try:
            with open(scenario_file, "r", encoding="utf-8") as f:
                scenario_data = json.load(f)
        except Exception:
            scenario_data = None

    cache_data: Optional[dict] = None
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        except Exception:
            cache_data = None

    # Step 1 (triage, running)
    if incident.raw_alert_count:
        triage_1_text = f"Grouping {incident.raw_alert_count} alerts using the dependency map"
    else:
        triage_1_text = "Grouping alerts using the dependency map"

    # Step 2 (triage, done)
    triage_2_text = f"No dependency of {root_svc} is alerting, so {root_svc} is the root"

    # Step 3 (diagnose, running)
    diag_1_text = f"Reading last 50 log lines from {root_svc}-0"

    # Step 4 (diagnose, running)
    diag_2_text = f"Reading Kubernetes events for {root_svc}-0"

    # Step 5 (diagnose, running): memory trend
    if scenario_data:
        metrics = scenario_data.get("metrics", {}).get(root_svc, [])
        if metrics:
            last_pt = metrics[-1]
            mem_val = last_pt.get("mem_mb")
            fix = scenario_data.get("fix", {})
            limit = fix.get("from")
            if limit:
                diag_3_text = f"Checking the memory trend: {mem_val}Mi of {limit} limit"
            else:
                diag_3_text = f"Checking the memory trend: {mem_val}Mi"
        else:
            diag_3_text = "Checking the memory trend"
    else:
        diag_3_text = "Checking the memory trend"

    # Step 6 (diagnose, done): category matching
    category = None
    if cache_data and "rca" in cache_data:
        category = cache_data["rca"].get("category")

    if category:
        diag_4_text = f"Matching the evidence: {category}"
    else:
        diag_4_text = "Matching the evidence"

    steps = [
        ("triage", triage_1_text, "running"),
        ("triage", triage_2_text, "done"),
        ("diagnose", diag_1_text, "running"),
        ("diagnose", diag_2_text, "running"),
        ("diagnose", diag_3_text, "running"),
        ("diagnose", diag_4_text, "done"),
    ]

    for agent, text, status in steps:
        await emit("agent_step", {
            "agent": agent,
            "text": text,
            "status": status,
        })
        await asyncio.sleep(0.8)


async def run_pipeline(incident: Incident, adapter: ClusterAdapter) -> Incident:
    """
    Checkpoint 1 pipeline stub:
    Emits scripted investigation steps, loads cached RCA onto a copy of the incident,
    and returns with status 'analyzing'.
    """
    await emit_scripted_steps(incident.scenario, incident)

    cache_file = CACHE_DIR / f"{incident.scenario}.json"
    if not cache_file.exists():
        await emit("agent_step", {
            "agent": "diagnose",
            "text": "No analysis available for this scenario",
            "status": "failed",
        })
        return incident

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)

        incident_copy = incident.model_copy(deep=True)
        if "rca" in cache and cache["rca"]:
            incident_copy.rca = RCA(**cache["rca"])
        incident_copy.playbook = None
        incident_copy.status = "analyzing"
        return incident_copy
    except Exception:
        await emit("agent_step", {
            "agent": "diagnose",
            "text": "No analysis available for this scenario",
            "status": "failed",
        })
        return incident
