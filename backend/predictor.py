"""Crash Predictor: Estimates time-to-exhaustion from memory growth trends (Member 2, Task 3.1)"""

from typing import List, Optional
from backend.models import MetricPoint


def seconds_to_limit(points: List[MetricPoint], limit_mb: float) -> Optional[float]:
    """
    Fits a linear regression to the LAST 20 points (mem_mb versus t_s).
    - If fewer than 3 points or the slope is <= 0.01 MB/s -> None.
    - If the last mem_mb is already >= limit_mb -> 0.0.
    - Otherwise returns (limit_mb - predicted_current) / slope, never negative.
    """
    if len(points) < 3:
        return None

    # Take the last 20 points, sorted by timestamp
    pts = sorted(points, key=lambda p: p.t_s)[-20:]
    if len(pts) < 3:
        return None

    last_pt = pts[-1]
    if last_pt.mem_mb >= limit_mb:
        return 0.0

    n = len(pts)
    sum_t = sum(p.t_s for p in pts)
    sum_m = sum(p.mem_mb for p in pts)
    mean_t = sum_t / n
    mean_m = sum_m / n

    denom = sum((p.t_s - mean_t) ** 2 for p in pts)
    if denom == 0.0:
        return None

    slope = sum((p.t_s - mean_t) * (p.mem_mb - mean_m) for p in pts) / denom
    if slope <= 0.01:
        return None

    # Intercept a on the regression line: y = a + slope * t
    intercept = mean_m - slope * mean_t
    predicted_current = intercept + slope * last_pt.t_s

    if predicted_current >= limit_mb:
        return 0.0

    rem = (limit_mb - predicted_current) / slope
    return max(0.0, rem)
