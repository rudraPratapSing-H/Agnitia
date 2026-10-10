"""Agnitia End-to-End Smoke Test Script (Member 2, TASK 2.8 & TASK SMOKE/D12).

Runs end-to-end smoke verification against a running Agnitia backend:

Without --predictive:
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

With --predictive:
  CLI: python demo/smoke.py --predictive [--runs N] [--only leak|harmless] [--window MIN MAX] [--base URL]
  - Leak run:
    1. POST /api/reset
    2. Open /ws
    3. POST /api/chaos/slow_leak
    4. Collect events until healed_auto with phase "verified" (timeout 150s)
    5. Track: seconds to first prediction, seconds to applied and prob,
       any rolled_back, any auto_blocked, any service_update where postgres status is root_cause.
    6. Assert verified was seen, no rolled_back, no root_cause.
    7. If --window MIN MAX is given, assert applied time is in [MIN, MAX].
  - Harmless run:
    For healthy_spike and sawtooth in turn:
    1. POST /api/reset
    2. Open /ws
    3. POST /api/chaos/<scenario>
    4. Watch for 310 / SIM_SPEED seconds (default 1)
    5. Assert ZERO healed_auto and ZERO auto_blocked events.
  - Print one line per run (scenario, apply time, probability at apply, PASS/FAIL).
  - Exit non-zero on any failure.
  - Always POST /api/reset at the end.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import List, Optional, Tuple

import httpx
import websockets


# ── Reactive Smoke Test (db_oom) ─────────────────────────────────────────────

async def run_single_smoke(
    run_idx: int,
    base_url: str,
    ws_url: str,
    client: httpx.AsyncClient,
) -> Tuple[bool, float, str]:
    """Executes a single reactive smoke test run (db_oom).

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


# ── Predictive Smoke Test (slow_leak, healthy_spike, sawtooth) ───────────────

async def run_single_predictive_leak(
    run_idx: int,
    base_url: str,
    ws_url: str,
    client: httpx.AsyncClient,
    window: Optional[Tuple[float, float]] = None,
) -> Tuple[bool, Optional[float], Optional[float], str]:
    """Executes a single predictive leak run (slow_leak).

    Collects events until healed_auto with phase "verified" (timeout 150s).
    Tracks:
      - seconds from inject to first prediction event
      - seconds to phase "applied" and its probability
      - any rolled_back
      - any auto_blocked
      - any service_update where postgres status is root_cause

    Asserts:
      - verified was seen
      - no rolled_back
      - no root_cause
      - if window given, applied time is inside [MIN, MAX]

    Returns:
        (passed: bool, apply_time: Optional[float], apply_prob: Optional[float], message: str)
    """
    print(f"\n==========================================")
    print(f"  Starting Predictive Leak Run {run_idx} (slow_leak)")
    print(f"==========================================")
    run_start = time.time()

    ws_task = None
    ws_stop = asyncio.Event()
    ws_connected = asyncio.Event()
    msg_queue: asyncio.Queue[str] = asyncio.Queue()

    first_pred_time: Optional[float] = None
    apply_time: Optional[float] = None
    apply_prob: Optional[float] = None
    verified_seen = False
    rolled_back_seen = False
    auto_blocked_seen = False
    postgres_root_cause_seen = False
    healed_auto_events: List[dict] = []
    auto_blocked_events: List[dict] = []

    try:
        # 1. Reset
        print(f"[{run_idx}] 1. Resetting cluster state (POST /api/reset)...")
        reset_resp = await client.post(f"{base_url}/api/reset")
        reset_resp.raise_for_status()

        # 2. Open WebSocket
        print(f"[{run_idx}] 2. Opening WebSocket connection to {ws_url}...")

        async def ws_listener():
            try:
                async with websockets.connect(ws_url) as ws:
                    ws_connected.set()
                    while not ws_stop.is_set():
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                            await msg_queue.put(msg)
                        except asyncio.TimeoutError:
                            continue
            except (asyncio.CancelledError, websockets.ConnectionClosed):
                pass
            except Exception as e:
                print(f"[{run_idx}] Warning: WebSocket listener exception: {e}")

        ws_task = asyncio.create_task(ws_listener())

        try:
            await asyncio.wait_for(ws_connected.wait(), timeout=5.0)
            print(f"[{run_idx}] WebSocket connected successfully.")
        except asyncio.TimeoutError:
            raise RuntimeError(f"Timed out connecting to WebSocket at {ws_url}")

        # 3. Inject slow_leak
        print(f"[{run_idx}] 3. Injecting slow_leak (POST /api/chaos/slow_leak)...")
        inject_start = time.time()
        inject_resp = await client.post(f"{base_url}/api/chaos/slow_leak")
        inject_resp.raise_for_status()

        # 4. Collect events until healed_auto with phase "verified" (timeout 150s)
        print(f"[{run_idx}] 4. Collecting events until healed_auto phase 'verified' (timeout: 150s)...")
        while time.time() - inject_start < 150.0:
            try:
                msg_str = await asyncio.wait_for(msg_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            try:
                data = json.loads(msg_str)
            except Exception:
                continue

            ev_type = data.get("type")
            payload = data.get("payload", {})

            if ev_type == "prediction":
                if first_pred_time is None:
                    first_pred_time = time.time() - inject_start
                    p_val = payload.get("probability")
                    print(f"[{run_idx}] First prediction at {first_pred_time:.2f}s (prob: {p_val})")

            elif ev_type == "healed_auto":
                healed_auto_events.append(payload)
                phase = payload.get("phase")
                if phase == "applied":
                    if apply_time is None:
                        apply_time = time.time() - inject_start
                        apply_prob = payload.get("probability")
                        print(f"[{run_idx}] healed_auto applied at {apply_time:.2f}s (prob: {apply_prob})")
                elif phase == "verified":
                    verified_seen = True
                    verified_time = time.time() - inject_start
                    print(f"[{run_idx}] healed_auto verified at {verified_time:.2f}s")
                    break
                elif phase == "rolled_back":
                    rolled_back_seen = True
                    print(f"[{run_idx}] healed_auto rolled_back detected: {payload}")
                    break

            elif ev_type == "auto_blocked":
                auto_blocked_seen = True
                auto_blocked_events.append(payload)
                print(f"[{run_idx}] auto_blocked event detected: {payload.get('reasons')}")

            elif ev_type == "service_update":
                svc_id = payload.get("id") or payload.get("service")
                status = payload.get("status")
                if svc_id == "postgres" and status == "root_cause":
                    postgres_root_cause_seen = True
                    print(f"[{run_idx}] postgres status became root_cause!")
                    break

        # Drain any buffered events in queue
        while not msg_queue.empty():
            try:
                data = json.loads(msg_queue.get_nowait())
                ev_type = data.get("type")
                payload = data.get("payload", {})
                if ev_type == "healed_auto":
                    healed_auto_events.append(payload)
                    if payload.get("phase") == "rolled_back":
                        rolled_back_seen = True
                elif ev_type == "service_update":
                    svc_id = payload.get("id") or payload.get("service")
                    if svc_id == "postgres" and payload.get("status") == "root_cause":
                        postgres_root_cause_seen = True
            except Exception:
                pass

        # 5. Assertions
        assert not rolled_back_seen, f"healed_auto with phase 'rolled_back' was detected: {healed_auto_events}"
        assert not postgres_root_cause_seen, "postgres reached status 'root_cause' (unhealed failure)"
        assert verified_seen, "healed_auto with phase 'verified' was not seen (150s timeout reached)"

        if window is not None:
            assert apply_time is not None, "healed_auto phase 'applied' was never received"
            assert window[0] <= apply_time <= window[1], (
                f"Apply time {apply_time:.2f}s is outside window [{window[0]:.1f}, {window[1]:.1f}]"
            )

        elapsed_s = time.time() - run_start
        print(f"[{run_idx}] slow_leak finished in {elapsed_s:.2f}s (apply_time: {apply_time:.2f}s, prob: {apply_prob})")
        return True, apply_time, apply_prob, "OK"

    except Exception as exc:
        elapsed_s = time.time() - run_start
        print(f"[{run_idx}] ERROR: slow_leak run failed after {elapsed_s:.2f}s: {exc}")
        return False, apply_time, apply_prob, str(exc)

    finally:
        ws_stop.set()
        if ws_task and not ws_task.done():
            ws_task.cancel()
            try:
                await ws_task
            except (asyncio.CancelledError, Exception):
                pass


async def run_single_predictive_harmless(
    scenario: str,
    run_idx: int,
    base_url: str,
    ws_url: str,
    client: httpx.AsyncClient,
) -> Tuple[bool, Optional[float], Optional[float], str]:
    """Executes a single harmless run (healthy_spike or sawtooth).

    Watches for 310 / SIM_SPEED seconds and asserts ZERO healed_auto
    and ZERO auto_blocked events.

    Returns:
        (passed: bool, apply_time: Optional[float], apply_prob: Optional[float], message: str)
    """
    print(f"\n==========================================")
    print(f"  Starting Harmless Run {run_idx} ({scenario})")
    print(f"==========================================")
    run_start = time.time()

    ws_task = None
    ws_stop = asyncio.Event()
    ws_connected = asyncio.Event()
    msg_queue: asyncio.Queue[str] = asyncio.Queue()

    healed_auto_events: List[dict] = []
    auto_blocked_events: List[dict] = []

    try:
        # 1. Reset
        print(f"[{run_idx}] 1. Resetting cluster state (POST /api/reset)...")
        reset_resp = await client.post(f"{base_url}/api/reset")
        reset_resp.raise_for_status()

        # 2. Open WebSocket
        print(f"[{run_idx}] 2. Opening WebSocket connection to {ws_url}...")

        async def ws_listener():
            try:
                async with websockets.connect(ws_url) as ws:
                    ws_connected.set()
                    while not ws_stop.is_set():
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                            await msg_queue.put(msg)
                        except asyncio.TimeoutError:
                            continue
            except (asyncio.CancelledError, websockets.ConnectionClosed):
                pass
            except Exception as e:
                print(f"[{run_idx}] Warning: WebSocket listener exception: {e}")

        ws_task = asyncio.create_task(ws_listener())

        try:
            await asyncio.wait_for(ws_connected.wait(), timeout=5.0)
            print(f"[{run_idx}] WebSocket connected successfully.")
        except asyncio.TimeoutError:
            raise RuntimeError(f"Timed out connecting to WebSocket at {ws_url}")

        # 3. Read SIM_SPEED from environment (default 1)
        sim_speed_str = os.getenv("SIM_SPEED", "1.0")
        try:
            sim_speed = float(sim_speed_str)
            if sim_speed <= 0:
                sim_speed = 1.0
        except ValueError:
            sim_speed = 1.0
        watch_duration = 310.0 / sim_speed

        # 4. Inject scenario
        print(f"[{run_idx}] 3. Injecting {scenario} (POST /api/chaos/{scenario})...")
        inject_start = time.time()
        inject_resp = await client.post(f"{base_url}/api/chaos/{scenario}")
        inject_resp.raise_for_status()

        # 5. Watch for watch_duration seconds
        print(f"[{run_idx}] 4. Watching for {watch_duration:.1f}s (SIM_SPEED={sim_speed})...")
        while time.time() - inject_start < watch_duration:
            try:
                msg_str = await asyncio.wait_for(msg_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            try:
                data = json.loads(msg_str)
            except Exception:
                continue

            ev_type = data.get("type")
            payload = data.get("payload", {})

            if ev_type == "healed_auto":
                healed_auto_events.append(payload)
                print(f"[{run_idx}] UNEXPECTED healed_auto event in {scenario}: {payload}")

            elif ev_type == "auto_blocked":
                auto_blocked_events.append(payload)
                print(f"[{run_idx}] UNEXPECTED auto_blocked event in {scenario}: {payload}")

        # Drain any remaining messages
        while not msg_queue.empty():
            try:
                data = json.loads(msg_queue.get_nowait())
                ev_type = data.get("type")
                payload = data.get("payload", {})
                if ev_type == "healed_auto":
                    healed_auto_events.append(payload)
                elif ev_type == "auto_blocked":
                    auto_blocked_events.append(payload)
            except Exception:
                pass

        # 6. Assert ZERO healed_auto and ZERO auto_blocked
        assert len(healed_auto_events) == 0, (
            f"Expected 0 healed_auto events in {scenario}, got {len(healed_auto_events)}: {healed_auto_events}"
        )
        assert len(auto_blocked_events) == 0, (
            f"Expected 0 auto_blocked events in {scenario}, got {len(auto_blocked_events)}: {auto_blocked_events}"
        )

        elapsed_s = time.time() - run_start
        print(f"[{run_idx}] Harmless run {scenario} finished in {elapsed_s:.2f}s (0 healed_auto, 0 auto_blocked)")
        return True, None, None, "OK"

    except Exception as exc:
        elapsed_s = time.time() - run_start
        print(f"[{run_idx}] ERROR: Harmless run {scenario} failed after {elapsed_s:.2f}s: {exc}")
        return False, None, None, str(exc)

    finally:
        ws_stop.set()
        if ws_task and not ws_task.done():
            ws_task.cancel()
            try:
                await ws_task
            except (asyncio.CancelledError, Exception):
                pass


# ── Main Orchestration ───────────────────────────────────────────────────────

async def main_async(args: argparse.Namespace) -> int:
    base_url = args.base.rstrip("/")
    if base_url.startswith("https://"):
        ws_url = "wss://" + base_url[len("https://"):] + "/ws"
    elif base_url.startswith("http://"):
        ws_url = "ws://" + base_url[len("http://"):] + "/ws"
    else:
        ws_url = f"ws://{base_url}/ws"

    runs = max(1, args.runs)

    mode_desc = "Predictive" if args.predictive else "Reactive"
    print(f"Connecting to Agnitia ({mode_desc}) at {base_url} (WS: {ws_url}) for {runs} run(s)...")

    # Verify backend is reachable
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/blast-radius/redis")
            if resp.status_code != 200:
                print(f"Backend check returned status {resp.status_code}")
        except Exception as e:
            print(f"Error: Could not reach Agnitia backend at {base_url}: {e}")
            print("Ensure backend is running (e.g. uvicorn backend.main:app --port 8000)")
            return 1

    # 1. Non-predictive flow (behaves exactly as today)
    if not args.predictive:
        results: List[Tuple[int, bool, float, str]] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for i in range(1, runs + 1):
                    passed, elapsed, msg = await run_single_smoke(i, base_url, ws_url, client)
                    results.append((i, passed, elapsed, msg))
        finally:
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

    # 2. Predictive flow
    window = tuple(args.window) if args.window else None
    only = args.only
    # Results tuple: (scenario, run_idx, passed, apply_time, apply_prob, msg)
    predictive_results: List[Tuple[str, int, bool, Optional[float], Optional[float], str]] = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(1, runs + 1):
                # Leak scenario
                if only is None or only == "leak":
                    passed, apply_time, apply_prob, msg = await run_single_predictive_leak(
                        run_idx=i,
                        base_url=base_url,
                        ws_url=ws_url,
                        client=client,
                        window=window,
                    )
                    predictive_results.append(("slow_leak", i, passed, apply_time, apply_prob, msg))
                    apply_str = f"{apply_time:.2f}s" if apply_time is not None else "N/A"
                    prob_str = f"{apply_prob:.3f}" if apply_prob is not None else "N/A"
                    status_str = "PASS" if passed else "FAIL"
                    print(f"slow_leak, {apply_str}, {prob_str}, {status_str}")

                # Harmless scenarios: healthy_spike and sawtooth in turn
                if only is None or only == "harmless":
                    for scenario in ["healthy_spike", "sawtooth"]:
                        passed, apply_time, apply_prob, msg = await run_single_predictive_harmless(
                            scenario=scenario,
                            run_idx=i,
                            base_url=base_url,
                            ws_url=ws_url,
                            client=client,
                        )
                        predictive_results.append((scenario, i, passed, apply_time, apply_prob, msg))
                        status_str = "PASS" if passed else "FAIL"
                        print(f"{scenario}, N/A, N/A, {status_str}")
    finally:
        # Always POST /api/reset at the end
        print("\nCleanup: Resetting cluster state (POST /api/reset)...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{base_url}/api/reset")
                print("Cluster state reset completed.")
        except Exception as e:
            print(f"Warning: Failed to reset cluster during cleanup: {e}")

    # Summary report
    print("\n" + "=" * 55)
    print("      PREDICTIVE SMOKE TEST RESULTS SUMMARY")
    print("=" * 55)
    all_passed = True
    for scenario, idx, passed, apply_time, apply_prob, msg in predictive_results:
        apply_str = f"{apply_time:.2f}s" if apply_time is not None else "N/A"
        prob_str = f"{apply_prob:.3f}" if apply_prob is not None else "N/A"
        status_str = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"Run {idx:2d} [{scenario}]: {apply_str}, {prob_str}, {status_str} - {msg}")

    passed_count = sum(1 for _, _, p, _, _, _ in predictive_results if p)
    print("-" * 55)
    print(f"Total: {passed_count}/{len(predictive_results)} runs passed.")
    print("=" * 55)

    return 0 if all_passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agnitia end-to-end smoke test CLI (Member 2)"
    )
    parser.add_argument(
        "--predictive",
        action="store_true",
        default=False,
        help="Run predictive auto-heal smoke verification",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of smoke test runs to execute (default: 1)",
    )
    parser.add_argument(
        "--only",
        choices=["leak", "harmless"],
        default=None,
        help="Filter predictive scenarios to only 'leak' or 'harmless'",
    )
    parser.add_argument(
        "--window",
        nargs=2,
        type=float,
        default=None,
        metavar=("MIN", "MAX"),
        help="Expected window [MIN MAX] in seconds for phase 'applied'",
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
