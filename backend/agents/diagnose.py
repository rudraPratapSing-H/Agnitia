"""Diagnosis Agent: Analyzes service telemetry and generates root cause analysis with evidence"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import List, Optional

from backend.models import (
    RCA,
    LogLine,
    MetricPoint,
    K8sEvent,
    Incident,
)
from backend.adapters.base import ClusterAdapter
from backend.agents import llm

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "diagnose.txt"
CACHE_DIR = Path(__file__).resolve().parent / "cache"
SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def load_diagnose_prompt() -> str:
    """Loads the diagnosis system prompt from prompts/diagnose.txt."""
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    return (
        "You are Agnitia's diagnosis agent, an expert Kubernetes SRE. "
        "Find the root cause and return ONLY valid JSON matching the rca schema."
    )


def downsample_metrics(metrics: List[MetricPoint], max_points: int = 40) -> List[MetricPoint]:
    """
    Downsamples metrics evenly to at most max_points, always preserving
    the last point and the maximum point (by memory / CPU).
    """
    if len(metrics) <= max_points:
        return metrics

    last_pt = metrics[-1]
    max_pt = max(metrics, key=lambda m: (m.mem_mb, m.cpu_pct))

    # Evenly pick indices
    num_intermediate = max(1, max_points - 2)
    step = (len(metrics) - 1) / num_intermediate
    sampled_indices = {int(i * step) for i in range(num_intermediate)}
    selected = [metrics[i] for i in sorted(sampled_indices) if i < len(metrics) - 1]

    # Combine ensuring max and last are present
    pts_by_id = {id(p): p for p in selected}
    pts_by_id[id(max_pt)] = max_pt
    pts_by_id[id(last_pt)] = last_pt

    sorted_pts = sorted(pts_by_id.values(), key=lambda p: p.t_s)
    if len(sorted_pts) > max_points:
        sorted_pts = [p for p in sorted_pts if p is not max_pt and p is not last_pt][:max_points - 2] + [max_pt, last_pt]
        sorted_pts.sort(key=lambda p: p.t_s)

    return sorted_pts


def build_diagnose_payload(
    root_service: str,
    logs: List[LogLine],
    events: List[K8sEvent],
    metrics: List[MetricPoint],
) -> dict:
    """Builds the structured telemetry payload dictionary for the LLM."""
    last_50_logs = [
        {"line": log.line, "t_s": log.t_s, "text": log.text}
        for log in logs[-50:]
    ]

    service_events = [
        {"t_s": ev.t_s, "service": ev.service, "text": ev.text}
        for ev in events
        if ev.service == root_service or not ev.service
    ]

    sampled_metrics = downsample_metrics(metrics, max_points=40)
    metrics_data = [
        {"t_s": pt.t_s, "mem_mb": pt.mem_mb, "cpu_pct": pt.cpu_pct}
        for pt in sampled_metrics
    ]

    return {
        "root_service": root_service,
        "pod": f"{root_service}-0",
        "logs": last_50_logs,
        "events": service_events,
        "metrics": metrics_data,
    }


async def diagnose(
    root_service: str,
    logs: List[LogLine],
    events: List[K8sEvent],
    metrics: List[MetricPoint],
    *,
    timeout_s: float = 15.0,
) -> RCA:
    """
    Analyzes root service telemetry via LLM to generate an RCA with evidence.
    """
    system_prompt = load_diagnose_prompt()
    payload = build_diagnose_payload(root_service, logs, events, metrics)

    rca_obj = await llm.call_json(
        system_prompt=system_prompt,
        payload=payload,
        model_cls=RCA,
        timeout_s=timeout_s,
    )
    return rca_obj


async def diagnose_incident(incident: Incident, adapter: ClusterAdapter) -> RCA:
    """
    Adapter-friendly entrypoint: fetches telemetry from the cluster adapter
    and invokes diagnose. In DEMO_MODE=cache or fallback, returns cached RCA.
    """
    demo_mode = os.getenv("DEMO_MODE", "auto")
    scenario_id = incident.scenario

    cache_file = CACHE_DIR / f"{scenario_id}.json"
    cached_data = None
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            cached_data = json.load(f)

    if demo_mode == "cache":
        if cached_data and "rca" in cached_data:
            return RCA(**cached_data["rca"])

    try:
        logs = await adapter.get_logs(incident.root_service, lines=50)
        events = await adapter.get_events(incident.root_service)
        metrics = await adapter.get_metrics(incident.root_service)
        return await diagnose(incident.root_service, logs, events, metrics)
    except Exception:
        if cached_data and "rca" in cached_data:
            return RCA(**cached_data["rca"])
        raise


def run_cli():
    parser = argparse.ArgumentParser(description="Agnitia Diagnosis Agent CLI")
    parser.add_argument("--scenario", required=True, help="Scenario ID (e.g. db_oom, bad_config)")
    parser.add_argument("--save-cache", action="store_true", help="Save result to cache directory")
    args = parser.parse_args()

    scenario_file = SCENARIOS_DIR / f"{args.scenario}.json"
    if not scenario_file.exists():
        print(f"Error: Scenario file {scenario_file} does not exist.")
        return

    with open(scenario_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    root_svc = data.get("root_service", "postgres")
    raw_logs = data.get("logs", {}).get(root_svc, [])
    raw_events = data.get("events", [])
    raw_metrics = data.get("metrics", {}).get(root_svc, [])

    logs = [LogLine(line=l.get("line", i + 1), t_s=l.get("t_s", 0.0), text=l.get("text", "")) for i, l in enumerate(raw_logs)]
    events = [K8sEvent(t_s=e.get("t_s", 0.0), service=e.get("service", root_svc), text=e.get("text", "")) for e in raw_events]
    metrics = [MetricPoint(t_s=m.get("t_s", 0.0), mem_mb=m.get("mem_mb", 0.0), cpu_pct=m.get("cpu_pct", 0.0)) for m in raw_metrics]

    async def _main():
        rca = await diagnose(root_svc, logs, events, metrics)
        print("\n=== Diagnosis RCA ===")
        print(json.dumps(rca.model_dump(), indent=2))

        if args.save_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_target = CACHE_DIR / f"{args.scenario}.json"
            cache_payload = {"rca": rca.model_dump(), "playbook": None}
            with open(cache_target, "w", encoding="utf-8") as out_f:
                json.dump(cache_payload, out_f, indent=2)
            print(f"\nSaved cache to {cache_target}")

    asyncio.run(_main())


if __name__ == "__main__":
    run_cli()
