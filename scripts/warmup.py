#!/usr/bin/env python3
"""
Pre-Stage Warm-Up Verification Script (Task 4.8)
Runs a warm-up call through Agnitia's diagnosis and incident memory components
to ensure caches are primed and models are responsive before going on stage.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.agents.memory import match_similar_incident
from backend.agents.planner import plan_recovery
from backend.models import Incident


def main():
    print("=" * 60)
    print("  AGNITIA PRE-STAGE WARM-UP DRILL (Task 4.8)")
    print("=" * 60)

    # 1. Warm up incident memory
    print("1. Priming incident memory matcher...", end=" ")
    match = match_similar_incident("postgres", "PostgreSQL OOMKilled 137 out of memory")
    assert match is not None and match.id == "INC-087"
    print(f"[OK] (Matched {match.id} at {match.similarity*100:.0f}%)")

    # 2. Warm up planner agent
    print("2. Priming recovery planner engine...", end=" ")
    import asyncio
    fake_incident = Incident(
        id="INC-104",
        status="detected",
        scenario="db_oom",
        root_service="postgres",
        impacted_services=["auth-service", "payment-service", "api-gateway", "web-ui"],
        raw_alert_count=56,
        started_at="2026-10-09T03:14:10Z",
    )
    playbook = asyncio.run(plan_recovery(fake_incident))
    assert playbook is not None and len(playbook.steps) > 0
    print(f"[OK] (Plan generated with {len(playbook.steps)} sequenced steps)")

    print("=" * 60)
    print("ALL PRE-STAGE WARM-UP CHECKS PASSED: READY FOR THE STAGE")
    print("=" * 60)


if __name__ == "__main__":
    main()
