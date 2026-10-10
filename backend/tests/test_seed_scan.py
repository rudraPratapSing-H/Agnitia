"""Unit tests for backend/ml/seed_scan.py (TASK D13 / Member 2)."""

import argparse
import pytest

from backend.ml import config
from backend.ml.predict import Predictor
from backend.ml.seed_scan import (
    main,
    scan_leak,
    scan_harmless,
    print_leak_table,
)


def test_scan_leak_output_structure():
    """Verify scan_leak filters fail_t in [100, 110] and sorts by closeness to 50s."""
    predictor = Predictor()
    # Range 0..50 contains seed 31 which fails at 101.5 and alarms at 51.5
    results = scan_leak(0, 50, predictor)

    assert len(results) > 0
    for r in results:
        assert "seed" in r
        assert "fail_t" in r
        assert "alarm_t" in r
        assert "warning" in r
        assert "max_prob" in r
        assert 100.0 <= r["fail_t"] <= 110.0
        assert r["warning"] == round(r["fail_t"] - r["alarm_t"], 1)

    # Verify sorting by closeness of alarm_t to 50s
    diffs = [abs(r["alarm_t"] - 50.0) for r in results]
    assert diffs == sorted(diffs)


def test_scan_harmless_output_structure():
    """Verify scan_harmless returns streaks and identifies seeds that never reach PERSISTENCE."""
    predictor = Predictor()
    # Test spike on seeds 0..5
    records, never_reached = scan_harmless("spike", 0, 5, predictor)

    assert len(records) == 5
    for seed, max_streak, reached in records:
        assert isinstance(seed, int)
        assert isinstance(max_streak, int)
        assert reached == (max_streak >= config.PERSISTENCE)
        if not reached:
            assert seed in never_reached


def test_print_leak_table_runs_without_error(capsys):
    """Verify print_leak_table prints expected header and contents."""
    sample_results = [
        {"seed": 31, "fail_t": 101.5, "alarm_t": 51.5, "warning": 50.0, "max_prob": 0.999},
    ]
    print_leak_table(sample_results, limit=10)
    captured = capsys.readouterr().out
    assert "SLOW LEAK SEED SCAN" in captured
    assert "31" in captured
    assert "101.5" in captured
    assert "51.5" in captured
