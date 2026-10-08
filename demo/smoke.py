#!/usr/bin/env python3
"""
demo/smoke.py  -  Task 1.14 integration smoke test.
Verifies that POST /api/chaos/{scenario} -> POST /api/reset -> repeat
works 3 times in a row on the demo laptop without a 409 error.

Usage:
    python demo/smoke.py                  # defaults to db_oom, 3 rounds
    python demo/smoke.py bad_config 2     # 2 rounds of bad_config
"""

import asyncio
import sys
import time
import httpx

BASE = "http://localhost:8000"
DEFAULT_SCENARIO = "db_oom"
DEFAULT_ROUNDS = 3
PLAY_WAIT_S = 16   # db_oom duration_s=12 + buffer


async def check_health(client):
    r = await client.get("/api/health", timeout=5)
    r.raise_for_status()
    print(f"  v Health OK: {r.json()}")


async def inject(client, scenario):
    print(f"  -> POST /api/chaos/{scenario}")
    r = await client.post(f"/api/chaos/{scenario}", timeout=10)
    if r.status_code == 409:
        raise RuntimeError(f"409 Conflict on inject (scenario still playing): {r.json()}")
    r.raise_for_status()
    print(f"  v Inject accepted: {r.json()}")


async def reset(client):
    print("  -> POST /api/reset")
    r = await client.post("/api/reset", timeout=10)
    r.raise_for_status()
    print(f"  v Reset OK: {r.json()}")


async def get_latest_incident(client):
    r = await client.get("/api/incidents/latest", timeout=5)
    r.raise_for_status()
    return r.json()


async def wait_for_incident(client, timeout=PLAY_WAIT_S):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        inc = await get_latest_incident(client)
        if inc and inc.get("status") in ("analyzing", "awaiting_approval", "resolved"):
            print(f"  v Incident visible: id={inc['id']} status={inc['status']}")
            return
        await asyncio.sleep(1)
    print("  ! No incident found within timeout (scenario may still be running)")


async def run(scenario, rounds):
    print(f"\nSmoke test: {rounds} x (inject {scenario!r} -> wait -> reset)\n")
    async with httpx.AsyncClient(base_url=BASE) as client:
        await check_health(client)
        for i in range(1, rounds + 1):
            print(f"\n-- Round {i}/{rounds} ---")
            t0 = time.monotonic()
            await inject(client, scenario)
            await wait_for_incident(client)
            await reset(client)
            inc = await get_latest_incident(client)
            if inc is not None:
                print(f"  ! Expected null after reset but got: {inc}")
            else:
                print("  v Latest incident is null after reset")
            print(f"  v Round {i} complete in {time.monotonic()-t0:.1f}s")
    print(f"\nAll {rounds} rounds passed - Inject -> Reset -> Inject is stable.\n")


if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCENARIO
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_ROUNDS
    asyncio.run(run(scenario, rounds))
