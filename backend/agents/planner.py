"""Planner Agent: Constructs dependency-ordered recovery playbooks"""

import json
from pathlib import Path
from backend.models import Incident, Playbook, PlaybookStep
from backend.graph import topo_order
from backend.agents.autonomy import needs_approval, get_autonomy_level

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def reorder_playbook_by_topology(steps: list[PlaybookStep]) -> list[PlaybookStep]:
    """
    Guarantees safety by checking and enforcing topological ordering:
    dependencies must always be remediated before downstream services.
    """
    services_in_playbook = [s.service for s in steps]
    safe_service_order = topo_order(services_in_playbook)

    # Map each service to its priority rank in topological order
    rank_map = {svc: idx for idx, svc in enumerate(safe_service_order)}

    # Sort steps by topological rank of their service, preserving relative intra-service order
    sorted_steps = sorted(steps, key=lambda s: rank_map.get(s.service, 99))

    # Re-assign 1-based order index
    for idx, step in enumerate(sorted_steps, 1):
        step.order = idx

    return sorted_steps


async def plan_recovery(incident: Incident) -> Playbook:
    """
    Plans recovery playbook for the diagnosed incident.
    Loads approved template, enforces topological ordering, and applies autonomy policy.
    """
    cache_file = CACHE_DIR / f"{incident.scenario}.json"
    playbook_data = None
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            playbook_data = data.get("playbook")

    if not playbook_data:
        # Fallback default playbook
        steps = [
            PlaybookStep(
                order=1,
                service=incident.root_service,
                action="rollout_restart",
                risk="medium",
                requires_approval=True,
                verify="service healthy",
            )
        ]
        return Playbook(diff=None, steps=steps)

    steps = [PlaybookStep(**s) for s in playbook_data.get("steps", [])]

    # Enforce topological dependency ordering
    ordered_steps = reorder_playbook_by_topology(steps)

    # Apply autonomy rules
    level = get_autonomy_level()
    for s in ordered_steps:
        s.requires_approval = needs_approval(s, level)

    return Playbook(
        diff=playbook_data.get("diff"),
        steps=ordered_steps,
    )
