"""Agnitia End-to-End Smoke Test Script (Member 2, TASK 2.8).

Runs end-to-end smoke verification against a running Agnitia backend:
  1. POST /api/reset
  2. Open /ws and count `alert` events
  3. POST /api/chaos/db_oom
  4. Poll GET /api/incidents/latest every 0.5s until status "awaiting_approval" (timeout 40s)
  5. Assert:
     - raw_alert_count == 56
     - root_service == "postgres"
     - set(impacted_services) == {"auth-service", "payment-service", "api-gateway", "web-ui"}
     - "redis" absent
     - WS saw exactly 56 alert events
  6. POST /api/incidents/{id}/approve
  7. Poll until status "resolved" (timeout 60s)
  8. Assert resolved_at is set
  9. Assert elapsed time <= 60s
  10. Print PASS/FAIL per run, elapsed seconds, and overall summary
  11. Always POST /api/reset at the end
"""

import argparse
import asyncio
import json
import sys
import time
from typing import List, Tuple

import httpx
import websockets


async def run_single_smoke(
    run_idx: int,
    base_url: str,
    ws_url: str,
    client: httpx.AsyncClient,
) -> Tuple[bool, float, str]:
    """Executes a single smoke test run.

    Returns:
        (passed: bool, elapsed_s: float, message: str)
    """
    print(f"\n==========================================")
    print(f"  Starting Smoke Test Run {run_idx}")
    print(f"==========================================")
    run_start = time.time()

    ws_task = None
    ws_stop = asyncio.Event()
    ws_connected = asyncio.Event()
    ws_alert_count = 0

    try:
        # 1. Reset
        print(f"[{run_idx}] 1. Resetting cluster state (POST /api/reset)...")
        reset_resp = await client.post(f"{base_url}/api/reset")
        reset_resp.raise_for_status()

        # 2. Open /ws and listen for alert events
        print(f"[{run_idx}] 2. Opening WebSocket connection to {ws_url}...")

        async def ws_listener():
            nonlocal ws_alert_count
            try:
                async with websockets.connect(ws_url) as ws:
                    ws_connected.set()
                    while not ws_stop.is_set():
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                            data = json.loads(msg)
                            if data.get("type") == "alert":
                                ws_alert_count += 1
                        except asyncio.TimeoutError:
                            continue
            except (asyncio.CancelledError, websockets.ConnectionClosed):
                pass
            except Exception as e:
                print(f"[{run_idx}] Warning: WebSocket listener exception: {e}")

        ws_task = asyncio.create_task(ws_listener())

        # Ensure WebSocket is connected before injecting chaos
        try:
            await asyncio.wait_for(ws_connected.wait(), timeout=5.0)
            print(f"[{run_idx}] WebSocket connected successfully.")
        except asyncio.TimeoutError:
            raise RuntimeError(f"Timed out connecting to WebSocket at {ws_url}")

        # 3. Inject db_oom scenario
        print(f"[{run_idx}] 3. Injecting chaos (POST /api/chaos/db_oom)...")
        inject_resp = await client.post(f"{base_url}/api/chaos/db_oom")
        inject_resp.raise_for_status()

        # 4. Poll GET /api/incidents/latest until status == 'awaiting_approval' (timeout 40s)
        print(f"[{run_idx}] 4. Polling GET /api/incidents/latest for 'awaiting_approval' (timeout: 40s)...")
        incident = None
        poll_start = time.time()
        while time.time() - poll_start < 40.0:
            resp = await client.get(f"{base_url}/api/incidents/latest")
            if resp.status_code == 200:
                data = resp.json()
                if data and data.get("status") == "awaiting_approval":
                    incident = data
                    break
            await asyncio.sleep(0.5)

        if not incident:
            raise AssertionError("Timed out waiting for incident status 'awaiting_approval' (40s limit reached)")

        print(f"[{run_idx}] Incident {incident['id']} reached 'awaiting_approval'.")

        # Give WebSocket a moment to catch up on any buffered alert packets
        ws_deadline = time.time() + 3.0
        while ws_alert_count < 56 and time.time() < ws_deadline:
            await asyncio.sleep(0.1)

        ws_stop.set()
        if ws_task and not ws_task.done():
            ws_task.cancel()
            try:
                await ws_task
            except (asyncio.CancelledError, Exception):
                pass

        # 5. Assertions
        print(f"[{run_idx}] 5. Verifying incident invariants and WebSocket alert count...")
        raw_count = incident.get("raw_alert_count")
        root_svc = incident.get("root_service")
        impacted_set = set(incident.get("impacted_services", []))
        expected_impacted = {"auth-service", "payment-service", "api-gateway", "web-ui"}

        print(f"     * raw_alert_count: {raw_count} (expected 56)")
        print(f"     * root_service: {root_svc} (expected 'postgres')")
        print(f"     * impacted_services: {impacted_set}")
        print(f"     * WS alert events received: {ws_alert_count} (expected 56)")

        assert raw_count == 56, f"raw_alert_count was {raw_count}, expected 56"
        assert root_svc == "postgres", f"root_service was '{root_svc}', expected 'postgres'"
        assert impacted_set == expected_impacted, (
            f"impacted_services was {impacted_set}, expected {expected_impacted}"
        )
        assert "redis" not in impacted_set, "redis must be absent from impacted_services"
        assert ws_alert_count == 56, (
            f"WebSocket saw {ws_alert_count} alert events, expected exactly 56"
        )

        # 6. POST approve
        incident_id = incident["id"]
        print(f"[{run_idx}] 6. Approving incident {incident_id} (POST /api/incidents/{incident_id}/approve)...")
        approve_resp = await client.post(
            f"{base_url}/api/incidents/{incident_id}/approve",
            json={"approved_by": "smoke-test"},
        )
        approve_resp.raise_for_status()

        # 7. Poll until "resolved" (timeout 60s)
        print(f"[{run_idx}] 7. Polling for incident resolution (timeout: 60s)...")
        resolved_incident = None
        resolve_start = time.time()
        while time.time() - resolve_start < 60.0:
            resp = await client.get(f"{base_url}/api/incidents/latest")
            if resp.status_code == 200:
                data = resp.json()
                if data and data.get("status") == "resolved":
                    resolved_incident = data
                    break
            await asyncio.sleep(0.5)

        if not resolved_incident:
            raise AssertionError(f"Timed out waiting for incident {incident_id} to be resolved (60s limit reached)")

        # 8. Assert resolved_at is set
        resolved_at = resolved_incident.get("resolved_at")
        print(f"[{run_idx}] 8. Incident resolved. resolved_at = {resolved_at}")
        assert resolved_at is not None and resolved_at != "", (
            f"Expected resolved_at to be non-empty, got {resolved_at}"
        )

        # 9. Elapsed time check
        elapsed_s = time.time() - run_start
        print(f"[{run_idx}] Run {run_idx} finished in {elapsed_s:.2f}s")
        if elapsed_s > 60.0:
            raise AssertionError(f"Run elapsed time {elapsed_s:.2f}s exceeded 60s limit")

        return True, elapsed_s, "OK"

    except Exception as exc:
        elapsed_s = time.time() - run_start
        print(f"[{run_idx}] ERROR: Run {run_idx} failed after {elapsed_s:.2f}s: {exc}")
        return False, elapsed_s, str(exc)

    finally:
        ws_stop.set()
        if ws_task and not ws_task.done():
            ws_task.cancel()
            try:
                await ws_task
            except (asyncio.CancelledError, Exception):
                pass


async def main_async(args: argparse.Namespace) -> int:
    base_url = args.base.rstrip("/")
    if base_url.startswith("https://"):
        ws_url = "wss://" + base_url[len("https://"):] + "/ws"
    elif base_url.startswith("http://"):
        ws_url = "ws://" + base_url[len("http://"):] + "/ws"
    else:
        ws_url = f"ws://{base_url}/ws"

    runs = max(1, args.runs)
    results: List[Tuple[int, bool, float, str]] = []

    print(f"Connecting to Agnetia at {base_url} (WS: {ws_url}) for {runs} run(s)...")

    # Verify backend is reachable
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/blast-radius/redis")
            if resp.status_code != 200:
                print(f"Backend check returned status {resp.status_code}")
        except Exception as e:
            print(f"Error: Could not reach Agnetia backend at {base_url}: {e}")
            print("Ensure backend is running (e.g. uvicorn backend.main:app --port 8000)")
            return 1

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(1, runs + 1):
                passed, elapsed, msg = await run_single_smoke(i, base_url, ws_url, client)
                results.append((i, passed, elapsed, msg))
                if not passed:
                    # Continue to remaining runs or record failure
                    pass
    finally:
        # Always POST /api/reset at the very end
        print("\nCleanup: Resetting cluster state (POST /api/reset)...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{base_url}/api/reset")
                print("Cluster state reset completed.")
        except Exception as e:
            print(f"Warning: Failed to reset cluster during cleanup: {e}")

    # Summary report
    print("\n" + "=" * 50)
    print("           SMOKE TEST RESULTS SUMMARY")
    print("=" * 50)
    all_passed = True
    for idx, passed, elapsed, msg in results:
        status_str = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"Run {idx:2d}: [{status_str}] in {elapsed:5.2f}s  - {msg}")

    passed_count = sum(1 for _, p, _, _ in results if p)
    print("-" * 50)
    print(f"Total: {passed_count}/{len(results)} runs passed.")
    print("=" * 50)

    return 0 if all_passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agnitia end-to-end smoke test CLI (Member 2)"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of smoke test runs to execute (default: 1)",
    )
    parser.add_argument(
        "--base",
        type=str,
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
