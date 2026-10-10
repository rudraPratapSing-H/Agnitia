"""Crash Predictor: Estimates time-to-exhaustion from memory growth trends (Member 2, Task P4-helper)."""

from typing import Any, List, Optional
import numpy as np


def _val(p: Any, key: str) -> float:
    """Helper to extract numeric value from either a dict or a MetricPoint object."""
    if isinstance(p, dict):
        return float(p[key])
    return float(getattr(p, key))


def seconds_to_limit(points: List[Any], limit_mb: float) -> Optional[float]:
    """
    Fits a linear regression to the LAST 20 points (mem_mb versus t_s).
    - If fewer than 3 points -> None.
    - Fits mem_mb versus t_s with np.polyfit.
    - If slope <= 0.01 MB/s -> None.
    - If last mem_mb >= limit_mb -> 0.0.
    - Otherwise returns (limit_mb - predicted_current) / slope, never negative, rounded to 1 decimal.
    """
    if len(points) < 3:
        return None

    # Take the last 20 points, sorted by timestamp
    pts = sorted(points, key=lambda p: _val(p, "t_s"))[-20:]
    if len(pts) < 3:
        return None

    last_pt = pts[-1]
    last_m = _val(last_pt, "mem_mb")
    if last_m >= limit_mb:
        return 0.0

    t_arr = np.array([_val(p, "t_s") for p in pts], dtype=float)
    m_arr = np.array([_val(p, "mem_mb") for p in pts], dtype=float)

    if np.all(t_arr == t_arr[0]):
        return None

    poly = np.polyfit(t_arr, m_arr, 1)
    slope = float(poly[0])
    intercept = float(poly[1])

    if slope <= 0.01:
        return None

    last_t = t_arr[-1]
    predicted_current = intercept + slope * last_t

    if predicted_current >= limit_mb:
        return 0.0

    rem = (limit_mb - predicted_current) / slope
    return round(float(max(0.0, rem)), 1)
