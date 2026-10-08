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

from backend.bus import bus, emit
from typing import Dict, Any

_metrics_buffer: Dict[str, List[MetricPoint]] = {}

async def _prediction_listener(envelope: Dict[str, Any]) -> None:
    if envelope.get("type") == "reset":
        _metrics_buffer.clear()
        return

    if envelope.get("type") != "metric_point":
        return

    payload = envelope["payload"]
    svc = payload["service"]
    t_s = payload["t_s"]
    mem_mb = payload["mem_mb"]
    cpu_pct = payload["cpu_pct"]

    if svc not in _metrics_buffer:
        _metrics_buffer[svc] = []
    
    _metrics_buffer[svc].append(MetricPoint(t_s=t_s, mem_mb=mem_mb, cpu_pct=cpu_pct, service=svc))
    
    # Keep only recent points to predict trend
    if len(_metrics_buffer[svc]) > 20:
        _metrics_buffer[svc].pop(0)
    
    # Predict limit for postgres (64.0 limit)
    if svc == "postgres":
        limit = 64.0
        sec = seconds_to_limit(_metrics_buffer[svc], limit)
        if sec is not None and 0 < sec < 300:
            import math
            mins = math.floor(sec / 60)
            secs = int(sec % 60)
            await emit("prediction", {
                "service": svc,
                "seconds": sec,
                "message": f"PostgreSQL memory trending to limit: estimated OOM crash in {mins}m {secs:02d}s"
            })

bus.add_listener(_prediction_listener)

