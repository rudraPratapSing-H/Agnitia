"""Configuration constants for predictive auto-healing (Member 2/3, TASK P1-P6)."""

from typing import List

# 7 features computed from the 30-second sliding window
FEATURES: List[str] = [
    "mem_frac",
    "mem_slope",
    "mem_accel",
    "cpu_frac",
    "restarts",
    "err_change",
    "mem_volatility",
]

# Simulator sampling and window parameters
STEP_S: float = 0.5          # Metrics sampled every 0.5s in simulator
WINDOW_S: float = 30.0       # Features computed from the last 30s
HORIZON_S: float = 90.0      # Label 1 if failure within the next 90s

# Policy and threshold parameters
PERSISTENCE: int = 5         # Consecutive scored windows required for alarm
THRESHOLD: float = 0.85       # Default model probability threshold
SUCCESS_P: float = 0.5       # Probability must drop below this after action to verify healthy
SAFE_TTL_S: float = 300.0    # Seconds to limit considered safe
VERIFY_TIMEOUT_S: int = 30   # Verification probe timeout in seconds
HOLD_AFTER_ACTION_S: float = 60.0  # Hold predictions for 60s after an action
