"""
backend/ml/make_data.py
P1b — build the windowed, labelled training dataset.

CLI:
    python -m backend.ml.make_data [--runs 600] [--seed 7] [--out backend/ml/data.csv]

A bare filename for --out (e.g. data_check.csv) is resolved to backend/ml/<filename>.
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from joblib import Parallel, delayed  # type: ignore

    _JOBLIB = True
except ImportError:  # pragma: no cover
    _JOBLIB = False

from backend.ml.config import FEATURES, HORIZON_S, WINDOW_S
from backend.ml.features import extract
from backend.ml.synth import KIND_COUNTS, KINDS, generate_run

# --------------------------------------------------------------------------- #
# Largest-remainder rounding                                                   #
# --------------------------------------------------------------------------- #

def _scaled_counts(n_runs: int) -> dict[str, int]:
    """Scale KIND_COUNTS proportionally to n_runs using largest-remainder rounding."""
    total_base = sum(KIND_COUNTS.values())  # 600
    exact = {k: v * n_runs / total_base for k, v in KIND_COUNTS.items()}
    floors = {k: math.floor(v) for k, v in exact.items()}
    remainder_needed = n_runs - sum(floors.values())
    # Sort by descending fractional part, break ties by KINDS order
    by_frac = sorted(
        KINDS,
        key=lambda k: (-(exact[k] - floors[k]), KINDS.index(k)),
    )
    counts: dict[str, int] = dict(floors)
    for k in by_frac[:remainder_needed]:
        counts[k] += 1
    return counts


# --------------------------------------------------------------------------- #
# Build one run's windows                                                      #
# --------------------------------------------------------------------------- #

def _windows_for_run(
    run_index: int,
    kind: str,
    rng: np.random.Generator,
) -> list[dict]:
    """Generate all labelled windows for a single run.

    Returns a list of row-dicts (possibly empty if no window passes MIN_POINTS).
    """
    points, fail_t = generate_run(kind, rng)

    # Build a dict keyed by t_s for O(1) slicing
    pts_by_t = {p["t_s"]: p for p in points}
    all_ts = [p["t_s"] for p in points]

    # End time for windowing:
    #   failing runs: up to and including floor(fail_t)
    #   healthy runs: up to the last point's t_s
    if fail_t is not None:
        t_max_window = math.floor(fail_t)
    else:
        t_max_window = int(all_ts[-1])  # 300 for healthy / spike / sawtooth

    run_id = f"r{run_index:04d}"
    fail_t_csv = fail_t if fail_t is not None else float("nan")

    rows: list[dict] = []
    # whole seconds t from WINDOW_S up to t_max_window (inclusive)
    for t in range(int(WINDOW_S), t_max_window + 1):
        # Points in the half-open window (t - WINDOW_S, t], i.e. t_s > t - WINDOW_S and t_s <= t
        lo = t - WINDOW_S
        window = [p for p in points if p["t_s"] > lo and p["t_s"] <= t]
        x = extract(window)
        if x is None:
            continue

        # Label: failing run whose failure is within HORIZON_S of this window's end
        if fail_t is not None and 0.0 <= fail_t - t <= HORIZON_S:
            label = 1
        else:
            label = 0

        row: dict = {
            "run_id": run_id,
            "kind": kind,
            "t_end": float(t),
            "fail_t": fail_t_csv,
        }
        for feature_name, value in zip(FEATURES, x.tolist()):
            row[feature_name] = value
        row["label"] = label
        rows.append(row)

    return rows


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def build_dataset(n_runs: int = 600, seed: int = 7) -> pd.DataFrame:
    """Build the windowed, labelled training dataset.

    Each run gets its own Generator spawned from SeedSequence(seed), so
    results are deterministic and independent of execution order.

    Returns a DataFrame with columns:
        run_id, kind, t_end, fail_t, <7 feature names>, label
    """
    counts = _scaled_counts(n_runs)

    # Build the flat list of (index, kind) assignments, respecting KINDS order
    assignments: list[tuple[int, str]] = []
    idx = 0
    for kind in KINDS:
        for _ in range(counts[kind]):
            assignments.append((idx, kind))
            idx += 1

    # One generator per run, all spawned from the same SeedSequence
    seed_seq = np.random.SeedSequence(seed)
    child_seeds = seed_seq.spawn(n_runs)
    rngs = [np.random.default_rng(s) for s in child_seeds]

    def _work(run_index: int, kind: str) -> list[dict]:
        return _windows_for_run(run_index, kind, rngs[run_index])

    if _JOBLIB and n_runs >= 50:
        results: list[list[dict]] = Parallel(n_jobs=-1)(
            delayed(_work)(i, k) for i, k in assignments
        )
    else:
        results = [_work(i, k) for i, k in assignments]

    # Concatenate in run-index order (already sorted by assignments)
    all_rows: list[dict] = []
    for rows in results:
        all_rows.extend(rows)

    columns = ["run_id", "kind", "t_end", "fail_t"] + FEATURES + ["label"]
    df = pd.DataFrame(all_rows, columns=columns)
    return df


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

_ML_DIR = Path(__file__).parent


def _resolve_out(out: str) -> Path:
    p = Path(out)
    if p.parent == Path("."):
        # Bare filename — resolve into backend/ml/
        return _ML_DIR / p.name
    return p


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Agnitia predictive auto-heal training dataset."
    )
    parser.add_argument("--runs", type=int, default=600)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=str, default="backend/ml/data.csv")
    args = parser.parse_args()

    t0 = time.perf_counter()
    df = build_dataset(n_runs=args.runs, seed=args.seed)
    elapsed = time.perf_counter() - t0

    out_path = _resolve_out(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    # Summary statistics
    counts = _scaled_counts(args.runs)
    print("Runs per kind:")
    for kind in KINDS:
        print(f"  {kind}: {counts[kind]}")
    total_windows = len(df)
    pos_share = df["label"].mean() * 100.0
    print(f"Total windows: {total_windows}")
    print(f"Positive-window share: {pos_share:.1f}%")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Written to: {out_path}")


if __name__ == "__main__":
    main()
