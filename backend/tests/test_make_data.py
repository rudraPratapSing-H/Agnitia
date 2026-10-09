"""
backend/tests/test_make_data.py
Tests for P1b: windowed dataset builder.
All tests use n_runs=30 for speed.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from backend.ml.config import FEATURES, HORIZON_S, WINDOW_S
from backend.ml.features import extract
from backend.ml.make_data import _scaled_counts, _windows_for_run, build_dataset
from backend.ml.synth import KIND_COUNTS, KINDS, generate_run

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

_SMALL = 30
_SEED = 42


def _build_small() -> pd.DataFrame:
    return build_dataset(n_runs=_SMALL, seed=_SEED)


# --------------------------------------------------------------------------- #
# Test 1 — columns and order                                                   #
# --------------------------------------------------------------------------- #

def test_columns_and_order():
    """DataFrame has exactly the right columns in the right order."""
    df = _build_small()
    expected = ["run_id", "kind", "t_end", "fail_t"] + FEATURES + ["label"]
    assert list(df.columns) == expected


# --------------------------------------------------------------------------- #
# Test 2 — no NaN in feature columns                                           #
# --------------------------------------------------------------------------- #

def test_no_nan_in_features():
    """No NaN values in the 7 feature columns (fail_t may be NaN for healthy kinds)."""
    df = _build_small()
    for col in FEATURES:
        assert df[col].notna().all(), f"NaN found in feature column '{col}'"


# --------------------------------------------------------------------------- #
# Test 3 — same seed gives identical frame                                     #
# --------------------------------------------------------------------------- #

def test_determinism():
    """Same seed produces byte-for-byte identical DataFrames."""
    df1 = build_dataset(n_runs=_SMALL, seed=_SEED)
    df2 = build_dataset(n_runs=_SMALL, seed=_SEED)
    pd.testing.assert_frame_equal(df1, df2, check_like=False)


# --------------------------------------------------------------------------- #
# Test 4 — label flip for a failing run                                        #
# --------------------------------------------------------------------------- #

def test_label_flips_at_horizon():
    """For one failing run, label==1 exactly when fail_t - t_end <= HORIZON_S."""
    # Find a failing run in the small dataset
    df = _build_small()
    failing = df[df["fail_t"].notna()].copy()
    assert len(failing) > 0, "No failing runs found in the sample"

    run_id = failing["run_id"].iloc[0]
    run_rows = failing[failing["run_id"] == run_id].copy()
    fail_t = run_rows["fail_t"].iloc[0]

    for _, row in run_rows.iterrows():
        t_end = row["t_end"]
        expected_label = 1 if 0.0 <= fail_t - t_end <= HORIZON_S else 0
        assert row["label"] == expected_label, (
            f"Label mismatch at t_end={t_end}, fail_t={fail_t}: "
            f"got {row['label']}, expected {expected_label}"
        )


# --------------------------------------------------------------------------- #
# Test 5 — NO LEAKAGE: features match a re-computed window from t_end points   #
# --------------------------------------------------------------------------- #

def test_no_leakage():
    """Re-computing features using only points up to t_end gives the same numbers."""
    df = _build_small()
    assert len(df) > 0

    # Sample one row deterministically (pick the middle row)
    sample_row = df.iloc[len(df) // 2]
    run_id = sample_row["run_id"]
    t_end = sample_row["t_end"]

    # Reconstruct the same run from scratch with the same generator
    run_index = int(run_id[1:])  # strip leading "r"
    seed_seq = np.random.SeedSequence(_SEED)
    child_seeds = seed_seq.spawn(_SMALL)
    rng = np.random.default_rng(child_seeds[run_index])

    # Determine the kind for this run_index
    counts = _scaled_counts(_SMALL)
    assignments: list[tuple[int, str]] = []
    idx = 0
    for kind in KINDS:
        for _ in range(counts[kind]):
            assignments.append((idx, kind))
            idx += 1
    _, kind = assignments[run_index]

    points, _ = generate_run(kind, rng)

    # Re-slice the same window: t_s in (t_end - WINDOW_S, t_end]
    lo = t_end - WINDOW_S
    window = [p for p in points if p["t_s"] > lo and p["t_s"] <= t_end]
    x = extract(window)
    assert x is not None, "Re-computed window returned None (too few points)"

    for feat_name, recomputed_val in zip(FEATURES, x.tolist()):
        stored_val = sample_row[feat_name]
        assert abs(stored_val - recomputed_val) < 1e-9, (
            f"Leakage/mismatch in '{feat_name}': "
            f"stored={stored_val}, recomputed={recomputed_val}"
        )


# --------------------------------------------------------------------------- #
# Test 6 — scaled counts still sum to n_runs                                   #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [30, 100, 600, 1])
def test_scaled_counts_sum(n: int):
    counts = _scaled_counts(n)
    assert sum(counts.values()) == n
    assert set(counts.keys()) == set(KINDS)


# --------------------------------------------------------------------------- #
# Test 7 — run_id format and uniqueness within a run                           #
# --------------------------------------------------------------------------- #

def test_run_id_format():
    """run_id follows the r{index:04d} format."""
    df = _build_small()
    run_ids = df["run_id"].unique()
    for rid in run_ids:
        assert rid.startswith("r")
        assert rid[1:].isdigit()
        assert len(rid) == 5  # 'r' + 4 digits
