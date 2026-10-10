"""
backend/tests/test_predict.py
Unit tests for TASK P4: live failure predictor.
"""
from __future__ import annotations

import numpy as np
import pytest

from backend.ml import config
from backend.ml.predict import Predictor
from backend.ml.synth import generate_run


def test_predictor_loads_model():
    """Predictor initializes and loads backend/ml/model.joblib by default."""
    pred = Predictor()
    assert pred.model is not None
    assert isinstance(pred.hist, dict)
    assert isinstance(pred.latest, dict)


def test_ingest_fewer_than_window_returns_none():
    """Ingesting fewer than ~30s of points returns None."""
    pred = Predictor()
    # 20 points (10s)
    for i in range(20):
        pt = {
            "service": "postgres",
            "t_s": i * 0.5,
            "mem_mb": 40.0 + i * 0.1,
            "mem_limit_mb": 64.0,
            "cpu_pct": 20.0,
            "restarts": 0,
            "err_pct": 0.1,
        }
        res = pred.ingest(pt)
        assert res is None
    assert len(pred.hist["postgres"]) == 20
    assert "postgres" not in pred.latest


def test_ingest_slow_leak_climbs_and_crosses_threshold():
    """Ingesting slow_leak run produces rising probabilities that cross THRESHOLD."""
    pred = Predictor()
    rng = np.random.default_rng(getattr(config, "DEMO_SEED", 42))
    points, fail_t = generate_run("slow_leak", rng, limit_mb=64.0)

    scored_probs = []
    for pt in points:
        pt_with_svc = dict(pt, service="postgres")
        p = pred.ingest(pt_with_svc)
        if p is not None:
            scored_probs.append((pt["t_s"], p))

    assert len(scored_probs) > 0
    # First scored probability (at ~30s) is relatively low (< 0.6)
    assert scored_probs[0][1] < 0.6
    # Final scored probabilities (near fail_t) are very high (> 0.9)
    assert scored_probs[-1][1] > 0.9
    # Crosses config.THRESHOLD
    thr = getattr(config, "THRESHOLD", 0.85)
    assert any(p >= thr for _, p in scored_probs)
    # Most recent is cached in latest
    assert pred.latest["postgres"] == pytest.approx(scored_probs[-1][1])


def test_ingest_healthy_spike_never_triggers_alarm():
    """Ingesting healthy_spike never exceeds config.THRESHOLD for PERSISTENCE consecutive windows."""
    pred = Predictor()
    rng = np.random.default_rng(getattr(config, "SPIKE_SEED", 1))
    points, _ = generate_run("spike", rng, limit_mb=64.0)

    thr = getattr(config, "THRESHOLD", 0.85)
    persistence = getattr(config, "PERSISTENCE", 5)

    streak = 0
    max_streak = 0
    for pt in points:
        pt_with_svc = dict(pt, service="postgres")
        p = pred.ingest(pt_with_svc)
        if p is not None:
            if p >= thr:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

    assert max_streak < persistence


def test_reset_clears_state():
    """reset() wipes all recorded history and latest predictions."""
    pred = Predictor()
    for i in range(10):
        pred.ingest({
            "service": "postgres",
            "t_s": i * 0.5,
            "mem_mb": 40.0,
            "mem_limit_mb": 64.0,
            "cpu_pct": 20.0,
            "restarts": 0,
            "err_pct": 0.0,
        })
    pred.latest["postgres"] = 0.42
    assert len(pred.hist["postgres"]) == 10

    pred.reset()
    assert len(pred.hist) == 0
    assert len(pred.latest) == 0
