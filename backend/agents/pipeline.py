"""Agent pipeline (tasks 2.1 + 2.4): triage -> evidence -> diagnose -> verify -> plan.

Streams agent_step events through backend.bus.emit and returns the incident with
rca + playbook and status "awaiting_approval".

DEMO_MODE is read on every call:
  live  - LLM only (no cache fallback)
  auto  - try live; on ANY error, or when one LLM call exceeds LLM_TIMEOUT_S, use the
          cached rca + playbook pair for the scenario
  cache - never call the LLM

Importing this module needs no LLM_API_KEY and no LLM SDK: llm / diagnose / planner are
imported lazily, and only on the live path.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import random
import time
from pathlib import Path

from backend.adapters.base import ClusterAdapter
from backend.agents.citations import verify_citations
from backend.models import (
    Incident,
    K8sEvent,
    LogLine,
    MetricPoint,
    Playbook,
    RCA,
    ServiceMetrics,
    ServiceNode,
    SimilarIncident,
)

try:
    from dotenv import load_dotenv

    # So DEMO_MODE from .env is visible even when llm.py (which also loads it) is never imported.
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

try:
    from backend.bus import emit
except ImportError:

    async def emit(type: str, payload: dict) -> None:
        print("[emit]", type, payload)


logging.basicConfig(level=logging.INFO)  # no-op when the app already configured logging
logger = logging.getLogger("agnitia.pipeline")

CACHE_DIR = Path(__file__).resolve().parent / "cache"
LLM_TIMEOUT_S = 4.0  # per LLM call (diagnose, plan); tests patch this
STEP_PACE_S = (0.6, 1.0)  # minimum gap between agent_step events; tests patch this
FAILED_TEXT = "No analysis available for this scenario"


# ── helpers ──────────────────────────────────────────────────────────────────


def _demo_mode() -> str:
    mode = os.getenv("DEMO_MODE", "auto").strip().lower()
    return mode if mode in ("auto", "cache", "live") else "auto"


def _kind(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError) or type(exc).__name__.endswith("Timeout"):
        return "timeout"
    return f"error:{type(exc).__name__}"


def _log_run(source: str, reason: str, t0: float) -> None:
    logger.info(
        "pipeline source=%s reason=%s total_ms=%d", source, reason, int((time.monotonic() - t0) * 1000)
    )


class _Steps:
    """Emits agent_step events at least STEP_PACE_S apart, so a cache run looks like a live run."""

    def __init__(self) -> None:
        self._last: float | None = None

    async def __call__(self, agent: str, text: str, status: str) -> None:
        if self._last is not None:
            lo, hi = STEP_PACE_S
            wait = random.uniform(lo, hi) - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
        try:
            await emit("agent_step", {"agent": agent, "text": text, "status": status})
        except Exception as exc:  # a broken socket must never break the pipeline
            logger.warning("emit failed: %s", exc)
        self._last = time.monotonic()


async def _timed(coro):
    """One LLM call, hard-limited to LLM_TIMEOUT_S."""
    return await asyncio.wait_for(coro, timeout=LLM_TIMEOUT_S)


async def _live_diagnose(root, logs, events, metrics) -> RCA:
    from backend.agents.diagnose import diagnose  # lazy: pulls in the LLM helper

    return await diagnose(root, logs, events, metrics)


async def _live_plan(rca: RCA, services) -> Playbook:
    from backend.agents.planner import plan  # lazy: pulls in the LLM helper

    return await plan(rca, services)


def _clean_live_rca(rca: RCA) -> RCA:
    """Never trust the model on similar_incident, warning or a percent-style confidence."""
    rca = rca.model_copy(deep=True)
    rca.similar_incident = None
    rca.warning = None
    conf = rca.confidence
    if 1 < conf <= 100:
        conf /= 100
    rca.confidence = round(min(1.0, max(0.0, conf)), 2)
    return rca


def _load_cache(scenario: str) -> tuple[RCA, Playbook] | None:
    path = CACHE_DIR / f"{Path(str(scenario)).name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rca = RCA.model_validate(data["rca"])
        for raw_step in data["playbook"]["steps"]:
            if raw_step.get("risk") not in ("low", "high"):  # contract allows low|high only
                raw_step["risk"], raw_step["requires_approval"] = "high", True
        playbook = Playbook.model_validate(data["playbook"])
    except Exception as exc:
        logger.warning("pipeline cache unusable for scenario=%s: %s", scenario, exc)
        return None
    if not playbook.steps:
        return None
    return rca, playbook


async def _cached_pair(incident: Incident, adapter: ClusterAdapter) -> tuple[RCA, Playbook] | None:
    """Cached rca + playbook, with the playbook re-checked against the allow-list and topo order."""
    loaded = _load_cache(incident.scenario)
    if loaded is None:
        return None
    rca, playbook = loaded
    try:
        from backend.agents.planner import DEFAULT_SERVICES, build_diff, reorder_and_process_steps
    except ImportError:
        return rca, playbook
    try:
        services = await adapter.list_services()
    except Exception:
        services = DEFAULT_SERVICES
    try:
        steps = reorder_and_process_steps([s.model_copy(deep=True) for s in playbook.steps], services)
    except Exception as exc:
        logger.warning("cached playbook rejected for scenario=%s: %s", incident.scenario, exc)
        return None
    return rca, Playbook(diff=playbook.diff or build_diff(steps), steps=steps)


async def _attach_similar(rca: RCA, root: str) -> RCA:
    """Incident memory lookup. Lazy import; a missing or broken memory module is ignored.

    Only overwrites rca.similar_incident when memory finds a match, so a cached match survives.
    """
    try:
        from backend.agents import memory
    except ImportError:
        return rca
    try:
        finder = getattr(memory, "find_similar", None)
        if finder is not None:
            found = finder(rca, root)
            if inspect.isawaitable(found):
                found = await found
        else:  # current memory.py API
            found = memory.match_similar_incident(root, f"{rca.root_cause} {rca.category}")
        if isinstance(found, dict):
            found = SimilarIncident.model_validate(found)
    except Exception as exc:
        logger.warning("incident memory lookup failed: %s", exc)
        return rca
    if found is not None:
        rca.similar_incident = found
    return rca


def _verify_text(rca: RCA) -> str:
    total = len(rca.evidence)
    if total == 0:
        return "No citations to check: the diagnosis cited no evidence"
    ok = sum(1 for e in rca.evidence if e.verified)
    text = f"Checked {total} citation{'s' if total != 1 else ''} against the raw data: {ok} verified"
    if ok < total:
        text += f", {total - ok} not found in the raw data"
    return text


def _unchanged(incident: Incident) -> Incident:
    out = incident.model_copy(deep=True)
    out.status = "analyzing"
    return out


async def _fail(step: _Steps, incident: Incident, stage: str, reason: str, t0: float) -> Incident:
    await step(stage, FAILED_TEXT, "failed")
    _log_run("none", reason, t0)
    return _unchanged(incident)


# ── pipeline ─────────────────────────────────────────────────────────────────


async def run_pipeline(incident: Incident, adapter: ClusterAdapter) -> Incident:
    """Triage -> evidence -> diagnose -> verify -> plan. Never raises."""
    t0 = time.monotonic()
    step = _Steps()
    try:
        return await _run(incident, adapter, step, t0)
    except Exception as exc:
        logger.exception("pipeline crashed")
        _log_run("none", f"unexpected_{type(exc).__name__}", t0)
        await step("diagnose", FAILED_TEXT, "failed")
        return _unchanged(incident)


async def _run(incident: Incident, adapter: ClusterAdapter, step: _Steps, t0: float) -> Incident:
    mode = _demo_mode()
    root = incident.root_service
    pod = f"{root}-0"

    # 1. TRIAGE (deterministic, no LLM)
    n_alerts = incident.raw_alert_count
    await step(
        "triage",
        f"Grouping {n_alerts} alerts using the dependency map"
        if n_alerts
        else "Grouping alerts using the dependency map",
        "running",
    )
    text = f"No dependency of {root} is alerting, so {root} is the root"
    if incident.impacted_services:
        text += f"; {len(incident.impacted_services)} downstream services impacted"
    await step("triage", text, "done")

    # 2. EVIDENCE (the "diagnose" chip lights up while the data is read)
    logs, events, metrics = [], [], []
    evidence_error: Exception | None = None
    try:
        logs = await adapter.get_logs(root, 50)
        await step("diagnose", f"Reading {len(logs)} log lines from {pod}", "running")
        events = await adapter.get_events(root)
        await step("diagnose", f"Reading {len(events)} Kubernetes events for {pod}", "running")
        metrics = await adapter.get_metrics(root)
        peak = max((m.mem_mb for m in metrics), default=0.0)
        await step(
            "diagnose",
            f"Checking the memory trend: {len(metrics)} metric points from {pod}, peak {peak:g}Mi",
            "running",
        )
    except Exception as exc:
        evidence_error = exc
        logger.warning("evidence collection failed: %s", exc)

    # 3. DIAGNOSE
    source, reason = "live", "ok"
    pair: tuple[RCA, Playbook] | None = None
    rca: RCA | None = None
    await step("diagnose", "Analysing logs, events and metrics to find the root cause", "running")
    if mode == "cache":
        source, reason = "cache", "demo_mode_cache"
    else:
        try:
            if evidence_error is not None:
                raise RuntimeError(f"evidence unavailable: {evidence_error}")
            rca = _clean_live_rca(await _timed(_live_diagnose(root, logs, events, metrics)))
        except Exception as exc:
            reason = f"diagnose_{_kind(exc)}"
            logger.warning("live diagnose failed (%s): %s", reason, exc)
            if mode == "live":
                return await _fail(step, incident, "diagnose", f"{reason}_live_only", t0)
            source = "cache"
    if source == "cache":
        pair = await _cached_pair(incident, adapter)
        if pair is None:
            return await _fail(step, incident, "diagnose", f"{reason}_no_cache", t0)
        rca = pair[0]
    await step("diagnose", f"Diagnosis complete: {rca.category} - {rca.root_cause}", "done")

    # 4. VERIFY citations against the raw data
    await step("verify", "Checking each citation against the raw logs, events and metrics", "running")
    rca = verify_citations(rca, logs, events, metrics)
    await step("verify", _verify_text(rca), "done")

    # 5. SIMILAR INCIDENT
    rca = await _attach_similar(rca, root)

    # 6. PLAN
    await step("plan", "Building the recovery plan, dependencies first", "running")
    if source == "live":
        try:
            services = await adapter.list_services()
            playbook = await _timed(_live_plan(rca, services))
        except Exception as exc:
            reason = f"plan_{_kind(exc)}"
            logger.warning("live plan failed (%s): %s", reason, exc)
            if mode == "live":
                return await _fail(step, incident, "plan", f"{reason}_live_only", t0)
            pair = await _cached_pair(incident, adapter)
            if pair is None:
                return await _fail(step, incident, "plan", f"{reason}_no_cache", t0)
            # Discard the live diagnosis: rca and playbook must come from the same source.
            source = "cache"
            rca = await _attach_similar(verify_citations(pair[0], logs, events, metrics), root)
            playbook = pair[1]
    else:
        playbook = pair[1]
    await step(
        "plan",
        f"Recovery plan ready: {len(playbook.steps)} steps" + (f" ({playbook.diff})" if playbook.diff else ""),
        "done",
    )

    # 7. DONE
    out = incident.model_copy(deep=True)
    out.rca = rca
    out.playbook = playbook
    out.status = "awaiting_approval"
    _log_run(source, reason, t0)
    return out


# ── CLI (Task 2.4b / 3.13: Refresh cache from scenarios) ────────────────────

CLI_SERVICES: list[ServiceNode] = [
    ServiceNode(
        id="web-ui",
        label="Web UI",
        tier="frontend",
        depends_on=["api-gateway"],
        status="healthy",
        metrics=ServiceMetrics(mem_mb=42, mem_limit_mb=128, cpu_pct=5, restarts=0),
    ),
    ServiceNode(
        id="api-gateway",
        label="API Gateway",
        tier="edge",
        depends_on=["auth-service", "payment-service"],
        status="healthy",
        metrics=ServiceMetrics(mem_mb=65, mem_limit_mb=128, cpu_pct=14, restarts=0),
    ),
    ServiceNode(
        id="auth-service",
        label="Auth Service",
        tier="backend",
        depends_on=["postgres", "redis"],
        status="healthy",
        metrics=ServiceMetrics(mem_mb=50, mem_limit_mb=128, cpu_pct=8, restarts=0),
    ),
    ServiceNode(
        id="payment-service",
        label="Payment Service",
        tier="backend",
        depends_on=["postgres"],
        status="healthy",
        metrics=ServiceMetrics(mem_mb=72, mem_limit_mb=128, cpu_pct=11, restarts=0),
    ),
    ServiceNode(
        id="postgres",
        label="PostgreSQL",
        tier="data",
        depends_on=[],
        status="healthy",
        metrics=ServiceMetrics(mem_mb=58, mem_limit_mb=64, cpu_pct=12, restarts=0),
    ),
    ServiceNode(
        id="redis",
        label="Redis",
        tier="data",
        depends_on=[],
        status="healthy",
        metrics=ServiceMetrics(mem_mb=24, mem_limit_mb=64, cpu_pct=3, restarts=0),
    ),
]


async def _refresh_scenario(scenario_path: Path) -> bool:
    """Refreshes cached RCA and Playbook for a single scenario file."""
    scenario_id = scenario_path.stem
    try:
        scenario_data = json.loads(scenario_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[{scenario_id}] Error reading scenario file: {exc}")
        return False

    root = scenario_data.get("root_service")
    if not root:
        print(f"[{scenario_id}] Error: root_service missing in scenario file")
        return False

    # 1. Build evidence: root service's last 50 logs, its events, its metrics
    raw_logs = scenario_data.get("logs", {}).get(root, [])
    logs = [
        LogLine(
            line=l.get("line", idx + 1),
            t_s=l.get("t_s", 0.0),
            text=l.get("text", ""),
            service=root,
        )
        for idx, l in enumerate(raw_logs)
    ][-50:]

    raw_events = scenario_data.get("events", [])
    events = [
        K8sEvent(
            t_s=e.get("t_s", 0.0),
            service=e.get("service", root),
            text=e.get("text", ""),
        )
        for e in raw_events
        if e.get("service") == root or not e.get("service")
    ]

    raw_metrics = scenario_data.get("metrics", {}).get(root, [])
    metrics = [
        MetricPoint(
            t_s=m.get("t_s", 0.0),
            mem_mb=m.get("mem_mb", 0.0),
            cpu_pct=m.get("cpu_pct", 0.0),
            service=root,
        )
        for m in raw_metrics
    ]

    # 2. Force a LIVE diagnose + plan, ignoring DEMO_MODE
    os.environ["DEMO_MODE"] = "live"

    from backend.agents import llm
    orig_call_json = llm.call_json

    async def _cli_call_json(*args, **kwargs):
        if kwargs.get("timeout_s", 4.0) <= 4.0:
            kwargs["timeout_s"] = 30.0
        return await orig_call_json(*args, **kwargs)

    llm.call_json = _cli_call_json

    try:
        raw_rca = await _live_diagnose(root, logs, events, metrics)
        rca = _clean_live_rca(raw_rca)

        # 3. Run verify_citations: require every evidence item verified=True and no warning
        verified_rca = verify_citations(rca, logs, events, metrics)
        unverified = [ev for ev in verified_rca.evidence if not ev.verified]
        if unverified or verified_rca.warning is not None:
            print(f"[{scenario_id}] Verification failed: warning={verified_rca.warning}")
            for item in unverified:
                print(f"  Offending evidence item: type={item.type} source={item.source} line={item.line} text={item.text!r}")
            return False

        verified_rca = await _attach_similar(verified_rca, root)
        playbook = await _live_plan(verified_rca, CLI_SERVICES)

        # 4. On success write backend/agents/cache/<id>.json as {"rca": ..., "playbook": ...}
        # with 2-space indent and trailing newline, and print one-line summary
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / f"{scenario_id}.json"
        cache_payload = {
            "rca": verified_rca.model_dump(mode="json"),
            "playbook": playbook.model_dump(mode="json"),
        }
        cache_path.write_text(json.dumps(cache_payload, indent=2) + "\n", encoding="utf-8")

        print(
            f"{scenario_id}: root_cause={verified_rca.root_cause!r} "
            f"confidence={verified_rca.confidence} "
            f"diff={playbook.diff!r}"
        )
        return True

    except Exception as exc:
        print(f"[{scenario_id}] Generation failed: {exc}")
        return False
    finally:
        llm.call_json = orig_call_json


def _cli_main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Refresh cached AI answers from the final prompts (TASK 2.4b / 3.13)"
    )
    parser.add_argument("--refresh-cache", action="store_true", help="Refresh cache for scenarios")
    parser.add_argument("--scenario", default=None, help="Optional scenario ID to refresh (e.g. db_oom)")
    args = parser.parse_args()

    if not args.refresh_cache:
        parser.print_help()
        sys.exit(1)

    scenarios_dir = Path(__file__).resolve().parents[1] / "scenarios"
    if args.scenario:
        scenario_files = [scenarios_dir / f"{args.scenario}.json"]
    else:
        scenario_files = sorted(scenarios_dir.glob("*.json"))

    if not scenario_files:
        print("No scenario files found.")
        sys.exit(1)

    has_failure = False
    for sf in scenario_files:
        if not sf.exists():
            print(f"Scenario file does not exist: {sf}")
            has_failure = True
            continue
        ok = asyncio.run(_refresh_scenario(sf))
        if not ok:
            has_failure = True

    if has_failure:
        sys.exit(1)


if __name__ == "__main__":
    _cli_main()

