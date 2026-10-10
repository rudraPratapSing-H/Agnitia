"""
backend/ml/predict.py
TASK P4 — Live failure predictor scoring services over sliding telemetry windows.
"""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from backend.ml.config import FEATURES, WINDOW_S
from backend.ml.features import extract

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "model.joblib"


class Predictor:
    """Live failure predictor: evaluates failure probability from metric windows."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        target_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
        if not target_path.exists():
            raise FileNotFoundError(f"Model file not found at {target_path}")

        self.model = joblib.load(target_path)
        self.hist: Dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
        self.latest: Dict[str, float] = {}

    def ingest(self, point: Dict[str, Any]) -> Optional[float]:
        """Ingests a metric point, updating history and scoring failure probability.

        Args:
            point: 7-key dictionary containing:
                service, t_s, mem_mb, mem_limit_mb, cpu_pct, restarts, err_pct.

        Returns:
            Probability of failure in [0.0, 1.0] if window is complete; otherwise None.
        """
        service = point.get("service")
        if not service:
            return None

        self.hist[service].append(point)

        history = list(self.hist[service])
        if len(history) < 5:
            return None

        curr_t = float(history[-1].get("t_s", 0.0))
        start_t = float(history[0].get("t_s", 0.0))

        # Check that we have a sufficiently populated window (~30s of metrics)
        if (curr_t - start_t) < (WINDOW_S - 1.0):
            return None

        # Filter points in the half-open window (curr_t - WINDOW_S, curr_t]
        lo = curr_t - WINDOW_S
        window = [p for p in history if float(p.get("t_s", 0.0)) > lo and float(p.get("t_s", 0.0)) <= curr_t]

        feats = extract(window)
        if feats is None:
            return None

        feats_df = pd.DataFrame([feats], columns=FEATURES)
        prob = float(self.model.predict_proba(feats_df)[0, 1])
        self.latest[service] = prob
        return prob

    def reset(self) -> None:
        """Clears metric history and latest prediction cache."""
        self.hist.clear()
        self.latest.clear()
