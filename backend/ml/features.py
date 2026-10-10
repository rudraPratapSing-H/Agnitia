"""Feature extraction over a sliding metrics window (Member 3, TASK P2)."""

from typing import Any, List, Optional
import numpy as np


def extract(window: List[dict]) -> Optional[np.ndarray]:
    """Computes a 7-feature vector from a sliding window of metric points.

    Features:
        1. mem_frac: Last memory usage as a fraction of its limit
        2. mem_slope: Linear regression slope of memory fraction over time (per second)
        3. mem_accel: Change in slope between second half and first half of the window
        4. cpu_frac: Last CPU percentage normalized to [0, 1]
        5. restarts: Total restarts observed in the window
        6. err_change: Change in error percentage from start to end of window
        7. mem_volatility: Standard deviation of memory fraction in the window

    Returns:
        np.ndarray of shape (7,) or None if window contains insufficient points.
    """
    if not window or len(window) < 5:
        return None

    t = np.array([p["t_s"] for p in window], dtype=float)
    limits = np.array([float(p.get("mem_limit_mb", 64.0)) for p in window], dtype=float)
    limits[limits <= 0] = 64.0
    mem_fracs = np.array([float(p["mem_mb"]) for p in window], dtype=float) / limits

    # 1. mem_frac
    mem_frac = float(mem_fracs[-1])

    # 2. mem_slope (per second)
    dt = t - t[0]
    if dt[-1] > 0 and len(window) >= 2:
        # Fast linear regression: cov(dt, mem_fracs) / var(dt)
        dt_mean = np.mean(dt)
        mem_mean = np.mean(mem_fracs)
        var_dt = np.sum((dt - dt_mean) ** 2)
        if var_dt > 1e-12:
            mem_slope = float(np.sum((dt - dt_mean) * (mem_fracs - mem_mean)) / var_dt)
        else:
            mem_slope = 0.0
    else:
        mem_slope = 0.0

    # 3. mem_accel (difference in slopes between second half and first half)
    half = len(window) // 2
    if half >= 2:
        dt1 = t[:half] - t[0]
        mf1 = mem_fracs[:half]
        v1 = np.sum((dt1 - np.mean(dt1)) ** 2)
        s1 = float(np.sum((dt1 - np.mean(dt1)) * (mf1 - np.mean(mf1))) / v1) if v1 > 1e-12 else 0.0

        dt2 = t[half:] - t[half]
        mf2 = mem_fracs[half:]
        v2 = np.sum((dt2 - np.mean(dt2)) ** 2)
        s2 = float(np.sum((dt2 - np.mean(dt2)) * (mf2 - np.mean(mf2))) / v2) if v2 > 1e-12 else 0.0
        mem_accel = float(s2 - s1)
    else:
        mem_accel = 0.0

    # 4. cpu_frac
    cpu_frac = float(window[-1].get("cpu_pct", 0.0)) / 100.0

    # 5. restarts
    restarts = float(window[-1].get("restarts", 0) - window[0].get("restarts", 0))

    # 6. err_change
    err_change = float(window[-1].get("err_pct", 0.0) - window[0].get("err_pct", 0.0))

    # 7. mem_volatility
    mem_volatility = float(np.std(mem_fracs))

    return np.array(
        [
            mem_frac,
            mem_slope,
            mem_accel,
            cpu_frac,
            restarts,
            err_change,
            mem_volatility,
        ],
        dtype=float,
    )
