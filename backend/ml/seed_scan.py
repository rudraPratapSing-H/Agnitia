"""backend/ml/seed_scan.py
TASK D13 — Seed scanner for slow_leak, spike, and sawtooth demo tuning.

CLI:
  python -m backend.ml.seed_scan --leak --range 0 300
  python -m backend.ml.seed_scan --harmless --range 0 50
"""

import argparse
import sys
from typing import List, Optional, Tuple

import numpy as np

from backend.ml import config
from backend.ml.predict import Predictor
from backend.ml.synth import generate_run


def scan_leak(start: int, end: int, predictor: Optional[Predictor] = None) -> List[dict]:
    """Scan slow_leak runs across seeds in [start, end) for demo candidates.

    Keeps only seeds where fail_t is between 100 and 110 s.
    Replays points through Predictor().ingest() to find alarm time:
    first moment probability >= config.THRESHOLD for config.PERSISTENCE consecutive windows.

    Returns:
        List of dicts sorted by closeness of alarm_t to 50 s:
        [{"seed": int, "fail_t": float, "alarm_t": float, "warning": float, "max_prob": float}]
    """
    if predictor is None:
        predictor = Predictor()

    results: List[dict] = []

    for seed in range(start, end):
        rng = np.random.default_rng(seed)
        points, fail_t = generate_run("slow_leak", rng)

        if fail_t is None or not (100.0 <= fail_t <= 110.0):
            continue

        predictor.reset()
        streak = 0
        alarm_t: Optional[float] = None
        max_prob = 0.0

        for pt in points:
            point_payload = {**pt, "service": "postgres"}
            prob = predictor.ingest(point_payload)

            if prob is not None:
                if prob > max_prob:
                    max_prob = prob

                if prob >= config.THRESHOLD:
                    streak += 1
                    if streak >= config.PERSISTENCE and alarm_t is None:
                        alarm_t = float(pt["t_s"])
                else:
                    streak = 0

        if alarm_t is not None:
            warning = fail_t - alarm_t
            results.append(
                {
                    "seed": seed,
                    "fail_t": round(fail_t, 1),
                    "alarm_t": round(alarm_t, 1),
                    "warning": round(warning, 1),
                    "max_prob": round(max_prob, 3),
                }
            )

    results.sort(key=lambda r: abs(r["alarm_t"] - 50.0))
    return results


def print_leak_table(results: List[dict], limit: int = 10) -> None:
    """Prints formatted table of top slow_leak candidates sorted by alarm_t closest to 50s."""
    top = results[:limit]
    print(f"\n{'=' * 65}")
    print("  SLOW LEAK SEED SCAN (100 <= fail_t <= 110, target alarm ~50s)")
    print(f"{'=' * 65}")
    print(f"{'seed':>6}  {'fail_t (s)':>10}  {'alarm_t (s)':>11}  {'warning (s)':>11}  {'max probability':>15}")
    print(f"{'-' * 65}")

    if not top:
        print("  No matching seeds found in the specified range.")
    else:
        for r in top:
            print(
                f"{r['seed']:>6}  {r['fail_t']:>10.1f}  {r['alarm_t']:>11.1f}  "
                f"{r['warning']:>11.1f}  {r['max_prob']:>15.3f}"
            )
    print(f"{'=' * 65}")
    if top:
        best = top[0]
        print(
            f"Best seed: {best['seed']} (fail_t={best['fail_t']}s, alarm_t={best['alarm_t']}s, "
            f"warning={best['warning']}s, max_p={best['max_prob']})\n"
        )


def scan_harmless(
    kind: str,
    start: int,
    end: int,
    predictor: Optional[Predictor] = None,
) -> Tuple[List[Tuple[int, int, bool]], List[int]]:
    """Scan harmless scenario ('spike' or 'sawtooth') across seeds.

    Replays points through Predictor().ingest(), finds highest streak reached
    and whether it reached config.PERSISTENCE.

    Returns:
        (records: list of (seed, max_streak, reached),
         never_reached: list of seeds where reached is False)
    """
    if predictor is None:
        predictor = Predictor()

    records: List[Tuple[int, int, bool]] = []
    never_reached: List[int] = []

    print(f"\n{'=' * 50}")
    print(f"  HARMLESS SEED SCAN: {kind.upper()} (seeds {start}..{end - 1})")
    print(f"{'=' * 50}")
    print(f"{'seed':>6}  {'max_streak':>12}  {'reached PERSISTENCE':>20}")
    print(f"{'-' * 50}")

    for seed in range(start, end):
        rng = np.random.default_rng(seed)
        points, _ = generate_run(kind, rng)

        predictor.reset()
        streak = 0
        max_streak = 0

        for pt in points:
            point_payload = {**pt, "service": "postgres"}
            prob = predictor.ingest(point_payload)

            if prob is not None:
                if prob >= config.THRESHOLD:
                    streak += 1
                    if streak > max_streak:
                        max_streak = streak
                else:
                    streak = 0

        reached = max_streak >= config.PERSISTENCE
        records.append((seed, max_streak, reached))
        if not reached:
            never_reached.append(seed)

        print(f"{seed:>6}  {max_streak:>12}  {str(reached):>20}", flush=True)

    print(f"{'-' * 50}")
    print(f"Seeds that never reached PERSISTENCE for '{kind}' ({len(never_reached)} total):")
    print(f"  {never_reached}\n", flush=True)
    return records, never_reached


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agnitia ML seed scanner for leak & harmless scenario tuning (Member 2)"
    )
    parser.add_argument(
        "--leak",
        action="store_true",
        default=False,
        help="Scan slow_leak seeds for optimal demo parameters (target alarm ~50s, fail 100-110s)",
    )
    parser.add_argument(
        "--harmless",
        action="store_true",
        default=False,
        help="Scan spike and sawtooth seeds to verify streak never reaches PERSISTENCE",
    )
    parser.add_argument(
        "--range",
        nargs=2,
        type=int,
        default=[0, 300],
        metavar=("START", "END"),
        help="Seed range [START END) to evaluate (default: 0 300 for leak, 0 50 for harmless)",
    )

    args = parser.parse_args()

    run_leak = args.leak
    run_harmless = args.harmless
    if not run_leak and not run_harmless:
        run_leak = True

    predictor = Predictor()

    if run_leak:
        start, end = args.range[0], args.range[1]
        results = scan_leak(start, end, predictor)
        print_leak_table(results, limit=10)

    if run_harmless:
        start, end = args.range[0], args.range[1]
        for kind in ["spike", "sawtooth"]:
            scan_harmless(kind, start, end, predictor)


if __name__ == "__main__":
    main()
