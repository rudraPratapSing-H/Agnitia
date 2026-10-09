import numpy as np
import pytest
from backend.ml.synth import KINDS, KIND_COUNTS, generate_run


def test_determinism_and_seed_variation():
    """1. Same kind and seed gives identical output; different seeds differ."""
    for kind in KINDS:
        pts1, fail1 = generate_run(kind, np.random.default_rng(42))
        pts2, fail2 = generate_run(kind, np.random.default_rng(42))
        pts3, fail3 = generate_run(kind, np.random.default_rng(99))

        assert pts1 == pts2
        assert fail1 == fail2
        assert pts1 != pts3 or fail1 != fail3


def test_harmless_runs_bounds_and_no_failure():
    """2. Over 20 seeds each, healthy, spike and sawtooth never reach 0.99 of the limit, spike peaks below 0.90, and fail_t is None."""
    limit_mb = 64.0
    for kind in ["healthy", "spike", "sawtooth"]:
        for seed in range(20):
            rng = np.random.default_rng(1000 + seed)
            pts, fail_t = generate_run(kind, rng, limit_mb=limit_mb)

            assert fail_t is None, f"{kind} produced non-None fail_t on seed {seed}"

            mem_fracs = [p["mem_mb"] / limit_mb for p in pts]
            max_frac = max(mem_fracs)

            assert (
                max_frac < 0.99
            ), f"{kind} reached >= 0.99 of limit ({max_frac}) on seed {seed}"

            if kind == "spike":
                assert (
                    max_frac < 0.90
                ), f"spike reached >= 0.90 ({max_frac}) on seed {seed}"


def test_failing_runs_properties():
    """3. slow_leak and fast_leak: fail_t inside its range, last t_s == fail_t, final mem_mb == limit_mb, earlier points below the limit. cpu_sat: last cpu_pct == 100 and fail_t == last t_s."""
    limit_mb = 64.0

    # slow_leak range: 90.0 to 260.0
    for seed in range(20):
        rng = np.random.default_rng(2000 + seed)
        pts, fail_t = generate_run("slow_leak", rng, limit_mb=limit_mb)
        assert fail_t is not None
        assert 90.0 <= fail_t <= 260.0
        assert pts[-1]["t_s"] == fail_t
        assert pts[-1]["mem_mb"] == limit_mb
        for p in pts[:-1]:
            assert p["mem_mb"] < limit_mb

    # fast_leak range: 40.0 to 90.0
    for seed in range(20):
        rng = np.random.default_rng(3000 + seed)
        pts, fail_t = generate_run("fast_leak", rng, limit_mb=limit_mb)
        assert fail_t is not None
        assert 40.0 <= fail_t <= 90.0
        assert pts[-1]["t_s"] == fail_t
        assert pts[-1]["mem_mb"] == limit_mb
        for p in pts[:-1]:
            assert p["mem_mb"] < limit_mb

    # cpu_sat: last cpu_pct == 100 and fail_t == last t_s
    for seed in range(20):
        rng = np.random.default_rng(4000 + seed)
        pts, fail_t = generate_run("cpu_sat", rng, limit_mb=limit_mb)
        assert fail_t is not None
        assert pts[-1]["cpu_pct"] == 100.0
        assert pts[-1]["t_s"] == fail_t


def test_schema_and_spacing():
    """4. Schema: all six keys on every point, t_s spaced exactly 0.5, healthy has 601 points."""
    expected_keys = {
        "t_s",
        "mem_mb",
        "mem_limit_mb",
        "cpu_pct",
        "restarts",
        "err_pct",
    }
    for kind in KINDS:
        rng = np.random.default_rng(5000)
        pts, _ = generate_run(kind, rng)
        assert len(pts) > 0
        assert pts[0]["t_s"] == 0.0

        for i, p in enumerate(pts):
            assert set(p.keys()) == expected_keys
            assert isinstance(p["t_s"], float)
            assert isinstance(p["mem_mb"], float)
            assert isinstance(p["mem_limit_mb"], float)
            assert isinstance(p["cpu_pct"], float)
            assert p["restarts"] == 0
            assert isinstance(p["err_pct"], float)

            if i > 0:
                dt = round(p["t_s"] - pts[i - 1]["t_s"], 3)
                assert dt == 0.5

        if kind == "healthy":
            assert len(pts) == 601


def test_kind_counts_sum():
    """5. KIND_COUNTS sums to 600."""
    assert sum(KIND_COUNTS.values()) == 600
    assert set(KIND_COUNTS.keys()) == set(KINDS)


def test_unknown_kind_raises_value_error():
    """Unknown kind -> ValueError."""
    rng = np.random.default_rng(42)
    with pytest.raises(ValueError):
        generate_run("unknown_failure", rng)
