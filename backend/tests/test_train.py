"""
backend/tests/test_train.py
Tests for TASK P3: model training, evaluation, persistence logic, and threshold sweep.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import List

import joblib
import numpy as np
import pandas as pd
import pytest

from backend.ml.config import FEATURES, PERSISTENCE
from backend.ml.train import (
    FAILING_KINDS,
    HARMLESS_KINDS,
    episodes,
    run_threshold_sweep,
    train_and_evaluate,
)


def _make_mock_episode_df(
    run_id: str,
    kind: str,
    probs: List[float],
    fail_t: float | None = 100.0,
    start_t: float = 30.0,
    step_s: float = 0.5,
) -> pd.DataFrame:
    """Creates a mock DataFrame for a single run_id."""
    n = len(probs)
    t_ends = [start_t + i * step_s for i in range(n)]
    rows = []
    for t_end, prob in zip(t_ends, probs):
        row = {
            "run_id": run_id,
            "kind": kind,
            "t_end": t_end,
            "fail_t": fail_t if kind in FAILING_KINDS else np.nan,
            "prob": prob,
            "label": 1 if (fail_t is not None and (fail_t - t_end) <= 90.0) else 0,
        }
        for f in FEATURES:
            row[f] = 0.5
        rows.append(row)
    return pd.DataFrame(rows)


def test_episodes_persistence_streak():
    """Alarm fires on the 5th consecutive window >= thr, not on 4 consecutive."""
    # 4 windows >= 0.85, then a dip, then 5 windows >= 0.85
    probs = [0.90, 0.90, 0.90, 0.90, 0.70, 0.90, 0.90, 0.90, 0.90, 0.90]
    df = _make_mock_episode_df("run_1", "slow_leak", probs, fail_t=100.0, start_t=30.0, step_s=1.0)

    ep_list = episodes(df, thr=0.85, persistence=5)
    assert len(ep_list) == 1
    run_id, kind, alarm_t, fail_t = ep_list[0]
    assert run_id == "run_1"
    assert kind == "slow_leak"
    assert fail_t == 100.0
    # Streak starts at index 5 (t=35.0): indices 5, 6, 7, 8, 9 (t=39.0 is the 5th)
    assert alarm_t == 39.0


def test_episodes_no_alarm_when_streak_broken():
    """If streak never reaches persistence threshold, alarm is None."""
    probs = [0.90, 0.90, 0.90, 0.90, 0.80, 0.90, 0.90]
    df = _make_mock_episode_df("run_2", "slow_leak", probs, fail_t=100.0)

    ep_list = episodes(df, thr=0.85, persistence=5)
    assert len(ep_list) == 1
    _, _, alarm_t, _ = ep_list[0]
    assert alarm_t is None


def test_run_threshold_sweep_metrics():
    """Threshold sweep correctly calculates caught %, false alarm rate, and suggested threshold."""
    # Create 1 failing run that triggers alarm and 1 healthy run that stays below threshold
    failing_probs = [0.95] * 10
    healthy_probs = [0.10] * 10
    df_failing = _make_mock_episode_df("run_fail", "slow_leak", failing_probs, fail_t=100.0, start_t=10.0, step_s=1.0)
    df_healthy = _make_mock_episode_df("run_heal", "healthy", healthy_probs, fail_t=None, start_t=10.0, step_s=1.0)
    test_df = pd.concat([df_failing, df_healthy], ignore_index=True)

    sweep_results, suggested_thr = run_threshold_sweep(test_df, persistence=5)
    assert len(sweep_results) == 50
    assert 0.50 <= suggested_thr <= 0.99

    # At threshold 0.80: failing is caught, healthy has 0 alarms
    stats_80 = next(s for s in sweep_results if s["thr"] == 0.80)
    assert stats_80["caught_pct"] == 1.0
    assert stats_80["false_alarm_rate"] == 0.0
    assert stats_80["median_warning_s"] > 0.0


def test_suggested_threshold_selection_criterion():
    """Suggested threshold is the lowest threshold whose false alarm rate is <= 2%."""
    # Create healthy run that triggers alarms between 0.50 and 0.70, but drops to 0 at 0.75
    harmless_probs = [0.72] * 10  # triggers persistence for thr <= 0.72
    fail_probs = [0.95] * 10
    df_harmless = _make_mock_episode_df("h1", "healthy", harmless_probs, fail_t=None)
    df_fail = _make_mock_episode_df("f1", "slow_leak", fail_probs, fail_t=100.0)
    test_df = pd.concat([df_harmless, df_fail], ignore_index=True)

    sweep_results, suggested_thr = run_threshold_sweep(test_df, persistence=5)
    # Lowest threshold where harmless alarms are 0 (<= 0.02) should be 0.73
    assert suggested_thr == 0.73


def test_train_and_evaluate_artifacts(tmp_path: Path):
    """train_and_evaluate produces valid joblib (<1MB), report.json, and report.md."""
    # Use existing backend/ml/data.csv if available
    data_path = Path("backend/ml/data.csv")
    if not data_path.exists():
        pytest.skip("backend/ml/data.csv not generated yet")

    out_model = tmp_path / "test_model.joblib"
    report_data = train_and_evaluate(
        data_path=str(data_path),
        seed=7,
        eval_only=False,
        out_model_path=str(out_model),
    )

    # 1. Model file exists and is well under 1MB
    assert out_model.exists()
    size_kb = out_model.stat().st_size / 1024.0
    assert size_kb < 1024.0, f"Model size {size_kb} KB exceeds 1024 KB limit"

    # 2. Report JSON
    report_json = tmp_path / "report.json"
    assert report_json.exists()
    with open(report_json, "r", encoding="utf-8") as f:
        loaded_json = json.load(f)
    assert "suggested_threshold" in loaded_json
    assert "metrics_at_suggested" in loaded_json
    assert "window_metrics" in loaded_json
    assert "feature_coefficients" in loaded_json
    assert "threshold_sweep" in loaded_json
    assert len(loaded_json["feature_coefficients"]) == len(FEATURES)

    # 3. Report Markdown
    report_md = tmp_path / "report.md"
    assert report_md.exists()
    content = report_md.read_text(encoding="utf-8")
    assert "# Agnitia Predictive Failure Detector" in content
    assert "Suggested Threshold" in content
    assert "Top Feature Weights" in content


def test_eval_only_loads_existing_model(tmp_path: Path):
    """When --eval-only is passed and model exists, it loads the model instead of refitting."""
    data_path = Path("backend/ml/data.csv")
    if not data_path.exists():
        pytest.skip("backend/ml/data.csv not generated yet")

    out_model = tmp_path / "model.joblib"
    # First fit
    train_and_evaluate(
        data_path=str(data_path),
        seed=7,
        eval_only=False,
        out_model_path=str(out_model),
    )
    mtime_1 = out_model.stat().st_mtime_ns

    # Second pass with eval_only=True
    train_and_evaluate(
        data_path=str(data_path),
        seed=7,
        eval_only=True,
        out_model_path=str(out_model),
    )
    mtime_2 = out_model.stat().st_mtime_ns
    assert mtime_1 == mtime_2, "Model was re-written during eval_only pass"
