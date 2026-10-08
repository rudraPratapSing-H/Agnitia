"""Smoke Test Script for Agnitia (Member 2)

Performs: Inject -> Wait -> Approve -> Assert Resolved.
"""

import asyncio
import httpx
import time
import sys

API_URL = "http://localhost:8000/api"

async def wait_for_incident_status(client: httpx.AsyncClient, incident_id: str, target_status: str, timeout_s: float = 30.0):
    start = time.time()
    while time.time() - start < timeout_s:
        resp = await client.get(f"{API_URL}/incidents/latest")
        resp.raise_for_status()
        data = resp.json()
        if data and data.get("id") == incident_id and data.get("status") == target_status:
            return data
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Incident {incident_id} did not reach status {target_status} within {timeout_s}s")

async def run_smoke_test(run_number: int):
    print(f"\n--- Starting Smoke Test Run {run_number} ---")
    async with httpx.AsyncClient() as client:
        # 1. Reset
        print("Resetting cluster...")
        await client.post(f"{API_URL}/reset")
        await asyncio.sleep(1)

        # 2. Inject
        print("Injecting db_oom scenario...")
        resp = await client.post(f"{API_URL}/chaos/db_oom")
        resp.raise_for_status()
        inj_data = resp.json()
        incident_id = inj_data["incident_id"]
        print(f"Injected incident: {incident_id}")

        # 3. Wait for awaiting_approval
        print(f"Waiting for {incident_id} to reach 'awaiting_approval'...")
        incident = await wait_for_incident_status(client, incident_id, "awaiting_approval", timeout_s=15.0)
        print("Incident is awaiting approval.")

        # 4. Approve
        print("Approving incident...")
        resp = await client.post(f"{API_URL}/incidents/{incident_id}/approve", json={"approved_by": "smoke-test"})
        resp.raise_for_status()

        # 5. Wait for resolved
        print(f"Waiting for {incident_id} to reach 'resolved'...")
        incident = await wait_for_incident_status(client, incident_id, "resolved", timeout_s=30.0)
        print(f"Success! Incident {incident_id} is resolved.")

async def main():
    try:
        # Check backend is up
        async with httpx.AsyncClient() as client:
            try:
                await client.get(f"{API_URL}/services")
            except httpx.ConnectError:
                print(f"Backend not running at {API_URL}. Start it with 'make dev' or 'make run-backend'.")
                sys.exit(1)

        for i in range(1, 4):
            start = time.time()
            await run_smoke_test(i)
            print(f"Run {i} completed in {time.time() - start:.1f}s")
            
        print("\nAll 3 smoke tests passed successfully!")
    except Exception as e:
        print(f"\nSmoke test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
