"""Planner Agent: Constructs dependency-ordered recovery playbooks"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from backend.models import Incident, Playbook, PlaybookStep, RCA, ServiceNode, ServiceMetrics
from backend.agents import llm

logger = logging.getLogger("agnitia.planner")

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "planner.txt"
CACHE_DIR = Path(__file__).resolve().parent / "cache"

ALLOWED_ACTIONS: set[str] = {
    "patch_memory_limit",
    "patch_cpu_limit",
    "rollout_restart",
    "rollback_deployment",
    "scale_replicas",
    "wait_for_ready",
    "verify_health",
}

HIGH_RISK_ACTIONS: set[str] = {
    "patch_memory_limit",
    "patch_cpu_limit",
    "rollback_deployment",
    "scale_replicas",
}

# The 6-service graph from CONTRACT.md section 7 as a constant
DEFAULT_SERVICES: list[ServiceNode] = [
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


class PlanError(Exception):
    """Raised when generated recovery playbook contains invalid or disallowed actions."""
    pass


def _kahn_topo_order(services: list[ServiceNode]) -> list[str]:
    """Fallback Kahn's algorithm using each service's depends_on (dependencies first)."""
    svc_ids = {s.id for s in services}
    deps_map = {s.id: [d for d in s.depends_on if d in svc_ids] for s in services}
    in_degree = {s_id: len(deps) for s_id, deps in deps_map.items()}

    dependents_map: dict[str, list[str]] = {s_id: [] for s_id in svc_ids}
    for s_id, deps in deps_map.items():
        for dep in deps:
            dependents_map[dep].append(s_id)

    current_level = sorted([s_id for s_id, deg in in_degree.items() if deg == 0])
    result: list[str] = []
    while current_level:
        next_level = []
        for u in current_level:
            result.append(u)
            for v in dependents_map[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    next_level.append(v)
        current_level = sorted(next_level)

    for s_id in sorted(svc_ids):
        if s_id not in result:
            result.append(s_id)

    return result


try:
    from backend.graph import topo_order as graph_topo_order

    def get_topo_order(services: list[ServiceNode]) -> list[str]:
        svc_ids = [s.id for s in services]
        try:
            return graph_topo_order(svc_ids)
        except Exception:
            return _kahn_topo_order(services)

except ImportError:
    def get_topo_order(services: list[ServiceNode]) -> list[str]:
        return _kahn_topo_order(services)


def build_diff(steps: list[PlaybookStep]) -> str:
    """Builds diff string from steps: do not trust the model."""
    diff_parts: list[str] = []
    for step in steps:
        params = step.params or {}
        if step.action == "patch_memory_limit":
            from_val = params.get("from", "")
            to_val = params.get("to", "")
            diff_parts.append(f"resources.limits.memory: {from_val} -> {to_val}")
        elif step.action == "patch_cpu_limit":
            from_val = params.get("from", "")
            to_val = params.get("to", "")
            diff_parts.append(f"resources.limits.cpu: {from_val} -> {to_val}")
        elif step.action == "rollback_deployment":
            diff_parts.append(f"rollback: previous revision of {step.service}")

    if diff_parts:
        return "; ".join(diff_parts)

    rollout_services: list[str] = []
    for step in steps:
        if step.action == "rollout_restart" and step.service not in rollout_services:
            rollout_services.append(step.service)

    if rollout_services:
        return f"No configuration change: rollout restart of {', '.join(rollout_services)}"

    return "No configuration change"


def reorder_and_process_steps(
    steps: list[PlaybookStep],
    services: list[ServiceNode],
) -> list[PlaybookStep]:
    """
    Validates actions, enforces high-risk attributes, and orders steps
    topologically with a stable sort.
    """
    # 2) VALIDATE: every action must be in ALLOWED_ACTIONS
    for step in steps:
        if step.action not in ALLOWED_ACTIONS:
            raise PlanError(f"Disallowed action: '{step.action}' is not in allowed actions list")

    # 3) FORCE: patch_memory_limit, patch_cpu_limit, rollback_deployment, scale_replicas
    # get risk "high" and requires_approval True, whatever the model said
    for step in steps:
        if step.action in HIGH_RISK_ACTIONS:
            step.risk = "high"
            step.requires_approval = True

    # 4) ORDER: reorder with a STABLE sort by the position of step.service in topo_order([service ids])
    # (dependencies first). Steps of the same service keep their relative order; unknown services go last.
    topo = get_topo_order(services)
    rank_map = {svc: idx for idx, svc in enumerate(topo)}

    sorted_steps = sorted(steps, key=lambda s: rank_map.get(s.service, 999999))

    # Renumber order 1..n
    for idx, step in enumerate(sorted_steps, 1):
        step.order = idx

    return sorted_steps


async def plan(rca: RCA, services: list[ServiceNode]) -> Playbook:
    """
    Constructs an incident recovery playbook.
    1) payload = the rca plus each service's id and depends_on. Call llm.call_json with Playbook model.
    2) VALIDATE: every action in allowed actions. Disallowed raises PlanError.
    3) FORCE: high risk and requires_approval True for patch/rollback/scale actions.
    4) ORDER: stable sort by topological dependency order (dependencies first), renumber order 1..n.
    5) DIFF: build diff from steps.
    """
    payload = {
        "rca": rca.model_dump() if hasattr(rca, "model_dump") else rca,
        "services": [
            {"id": s.id, "depends_on": list(s.depends_on)}
            for s in services
        ],
    }

    prompt_text = PROMPT_FILE.read_text(encoding="utf-8").strip() if PROMPT_FILE.exists() else (
        "Given the root cause and the dependency graph, produce a recovery playbook."
    )

    raw_playbook = await llm.call_json(prompt_text, payload, Playbook)

    copied_steps = [s.model_copy(deep=True) for s in raw_playbook.steps]
    ordered_steps = reorder_and_process_steps(copied_steps, services)
    diff = build_diff(ordered_steps)

    return Playbook(diff=diff, steps=ordered_steps)


async def plan_recovery(incident: Incident) -> Playbook:
    """
    Backward-compatible entrypoint using scenario incident.
    """
    cache_file = CACHE_DIR / f"{incident.scenario}.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            cached_rca = data.get("rca")
            cached_pb = data.get("playbook")
            if cached_pb:
                steps = [PlaybookStep(**s) for s in cached_pb.get("steps", [])]
                ordered_steps = reorder_and_process_steps(steps, DEFAULT_SERVICES)
                diff = build_diff(ordered_steps)
                return Playbook(diff=diff, steps=ordered_steps)
            if cached_rca:
                return await plan(RCA(**cached_rca), DEFAULT_SERVICES)

    # Fallback default step
    steps = [
        PlaybookStep(
            order=1,
            service=incident.root_service,
            action="rollout_restart",
            risk="low",
            requires_approval=False,
            verify="service healthy",
        )
    ]
    ordered_steps = reorder_and_process_steps(steps, DEFAULT_SERVICES)
    return Playbook(diff=build_diff(ordered_steps), steps=ordered_steps)


def run_cli():
    parser = argparse.ArgumentParser(description="Agnitia Planner Agent CLI")
    parser.add_argument("--scenario", default="db_oom", help="Scenario ID (default: db_oom)")
    args = parser.parse_args()

    cache_file = CACHE_DIR / f"{args.scenario}.json"
    if not cache_file.exists():
        print(f"Error: Cache file not found: {cache_file}")
        return

    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    rca_data = data.get("rca")
    if not rca_data:
        print(f"Error: No RCA found in {cache_file}")
        return

    rca = RCA(**rca_data)

    async def _main():
        demo_mode = os.getenv("DEMO_MODE", "auto")
        api_key = os.getenv("LLM_API_KEY", "").strip()

        if demo_mode == "cache" or not api_key or api_key == "your_llm_api_key_here":
            cached_pb_data = data.get("playbook")
            if cached_pb_data:
                steps = [PlaybookStep(**s) for s in cached_pb_data.get("steps", [])]
                ordered_steps = reorder_and_process_steps(steps, DEFAULT_SERVICES)
                diff = build_diff(ordered_steps)
                playbook = Playbook(diff=diff, steps=ordered_steps)
                print(json.dumps(playbook.model_dump(), indent=2))
                return

        try:
            playbook = await plan(rca, DEFAULT_SERVICES)
            print(json.dumps(playbook.model_dump(), indent=2))
        except Exception as e:
            cached_pb_data = data.get("playbook")
            if cached_pb_data:
                steps = [PlaybookStep(**s) for s in cached_pb_data.get("steps", [])]
                ordered_steps = reorder_and_process_steps(steps, DEFAULT_SERVICES)
                diff = build_diff(ordered_steps)
                playbook = Playbook(diff=diff, steps=ordered_steps)
                print(json.dumps(playbook.model_dump(), indent=2))
            else:
                raise e

    asyncio.run(_main())


if __name__ == "__main__":
    run_cli()
