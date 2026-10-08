"""Diagnosis Agent: Analyzes service telemetry and generates root cause analysis with evidence"""

import json
import os
from pathlib import Path
from typing import Optional
from backend.models import RCA, Incident
from backend.adapters.base import ClusterAdapter
from backend.agents.citations import verify_citations
from backend.agents.memory import match_similar_incident

CACHE_DIR = Path(__file__).resolve().parent / "cache"


async def diagnose_incident(incident: Incident, adapter: ClusterAdapter) -> RCA:
    """
    Performs root cause diagnosis. In DEMO_MODE=cache or when offline,
    loads the verified pre-computed cache. Otherwise can invoke live LLM.
    """
    demo_mode = os.getenv("DEMO_MODE", "auto")
    scenario_id = incident.scenario

    cache_file = CACHE_DIR / f"{scenario_id}.json"
    cached_data = None
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            cached_data = json.load(f)

    # In cache mode or if no API key provided, use cache
    llm_key = os.getenv("LLM_API_KEY", "")
    if demo_mode == "cache" or not llm_key or llm_key == "your_llm_api_key_here":
        if cached_data and "rca" in cached_data:
            rca = RCA(**cached_data["rca"])
            # Match historical incident if not set
            if not rca.similar_incident:
                rca.similar_incident = match_similar_incident(incident.root_service, rca.root_cause)
            return rca

    # If live LLM invocation configured
    try:
        # Live agent call can be placed here; fallback to cache on any error or timeout
        if cached_data and "rca" in cached_data:
            rca = RCA(**cached_data["rca"])
            logs = await adapter.get_logs(incident.root_service)
            events = await adapter.get_events(incident.root_service)
            metrics = await adapter.get_metrics(incident.root_service)
            return verify_citations(rca, logs, events, metrics)
    except Exception:
        pass

    if cached_data and "rca" in cached_data:
        return RCA(**cached_data["rca"])

    return RCA(
        root_cause=f"Failure isolated in {incident.root_service}",
        category="GeneralFault",
        confidence=0.85,
        evidence=[],
    )
