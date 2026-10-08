"""Crash Predictor: Estimates time-to-exhaustion from memory growth trends"""

from typing import List, Optional
from backend.models import MetricPoint


def seconds_to_limit(points: List[MetricPoint], limit_mb: float) -> Optional[float]:
    """
    Calculates estimated seconds until memory reaches limit_mb using linear regression slope.
    Returns None if slope <= 0 or insufficient points.
    """
    if len(points) < 2:
        return None

    # Sort points by timestamp
    sorted_pts = sorted(points, key=lambda p: p.t_s)
    last_pt = sorted_pts[-1]

    if last_pt.mem_mb >= limit_mb:
        return 0.0

    # Calculate linear slope (d_mem / dt)
    n = len(sorted_pts)
    sum_t = sum(p.t_s for p in sorted_pts)
    sum_m = sum(p.mem_mb for p in sorted_pts)
    sum_tm = sum(p.t_s * p.mem_mb for p in sorted_pts)
    sum_t2 = sum(p.t_s ** 2 for p in sorted_pts)

    denominator = (n * sum_t2 - sum_t ** 2)
    if denominator == 0:
        return None

    slope = (n * sum_tm - sum_t * sum_m) / denominator  # MB per second

    if slope <= 0:
        return None

    remaining_mb = limit_mb - last_pt.mem_mb
    seconds_remaining = remaining_mb / slope
    return round(seconds_remaining, 1)
