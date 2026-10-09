import numpy as np
from backend.ml.config import STEP_S

KINDS = ["slow_leak", "fast_leak", "cpu_sat", "healthy", "spike", "sawtooth"]
KIND_COUNTS = {
    "slow_leak": 150,
    "fast_leak": 48,
    "cpu_sat": 42,
    "healthy": 210,
    "spike": 90,
    "sawtooth": 60,
}


def _normal_cpu_and_err(
    n_points: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Helper generating normal baseline CPU (%) and err_pct values."""
    cpu_base = float(rng.uniform(15.0, 50.0))
    cpu_noise_std = float(rng.uniform(3.0, 6.0))
    cpu = np.clip(
        cpu_base + rng.normal(0.0, cpu_noise_std, size=n_points), 0.0, 100.0
    )
    err = np.maximum(0.0, rng.normal(0.4, 0.2, size=n_points))
    return cpu, err


def generate_run(
    kind: str, rng: np.random.Generator, limit_mb: float = 64.0
) -> tuple[list[dict], float | None]:
    """Generate synthetic timeseries metrics for a given service failure or health kind."""
    if kind not in KINDS:
        raise ValueError(f"Unknown kind '{kind}', expected one of {KINDS}")

    if kind == "slow_leak":
        start_frac = float(rng.uniform(0.35, 0.55))
        fail_t_raw = float(rng.uniform(90.0, 260.0))
        fail_t = float(
            np.clip(round(fail_t_raw / STEP_S) * STEP_S, 90.0, 260.0)
        )
        fail_t = round(fail_t, 3)
        n_points = int(round(fail_t / STEP_S)) + 1
        t_s = np.round(np.linspace(0.0, fail_t, n_points), 3)

        trend = start_frac + (1.0 - start_frac) * (t_s / fail_t)
        noise = rng.normal(0.0, 0.01, size=n_points)
        mem_frac = trend + noise
        mem_frac[:-1] = np.clip(mem_frac[:-1], 0.0, 0.999)
        mem_frac[-1] = 1.0

        cpu, err = _normal_cpu_and_err(n_points, rng)

    elif kind == "fast_leak":
        start_frac = float(rng.uniform(0.40, 0.60))
        fail_t_raw = float(rng.uniform(40.0, 90.0))
        fail_t = float(np.clip(round(fail_t_raw / STEP_S) * STEP_S, 40.0, 90.0))
        fail_t = round(fail_t, 3)
        n_points = int(round(fail_t / STEP_S)) + 1
        t_s = np.round(np.linspace(0.0, fail_t, n_points), 3)

        trend = start_frac + (1.0 - start_frac) * (t_s / fail_t)
        noise = rng.normal(0.0, 0.01, size=n_points)
        mem_frac = trend + noise
        mem_frac[:-1] = np.clip(mem_frac[:-1], 0.0, 0.999)
        mem_frac[-1] = 1.0

        cpu, err = _normal_cpu_and_err(n_points, rng)

    elif kind == "cpu_sat":
        mem_base = float(rng.uniform(0.40, 0.60))
        cpu_start = float(rng.uniform(25.0, 35.0))
        duration = float(rng.uniform(60.0, 150.0))
        err_target = float(rng.uniform(15.0, 25.0))

        t_list: list[float] = []
        mem_list: list[float] = []
        cpu_list: list[float] = []
        err_list: list[float] = []

        i = 0
        while True:
            t_curr = round(i * STEP_S, 3)
            cpu_trend = cpu_start + (100.0 - cpu_start) * (t_curr / duration)
            cpu_noise = float(rng.normal(0.0, 2.0))
            cpu_val = min(100.0, max(0.0, cpu_trend + cpu_noise))

            err_trend = 0.4 + (err_target - 0.4) * (t_curr / duration)
            err_noise = float(rng.normal(0.0, 0.2))
            err_val = max(0.0, err_trend + err_noise)

            mem_noise = float(rng.normal(0.0, 0.01))
            mem_val = max(0.0, mem_base + mem_noise)

            t_list.append(t_curr)
            mem_list.append(mem_val)
            err_list.append(err_val)

            if cpu_val >= 100.0 or cpu_trend + cpu_noise >= 100.0:
                cpu_list.append(100.0)
                fail_t = t_curr
                break
            else:
                cpu_list.append(cpu_val)
            i += 1

        t_s = np.array(t_list, dtype=float)
        mem_frac = np.array(mem_list, dtype=float)
        cpu = np.array(cpu_list, dtype=float)
        err = np.array(err_list, dtype=float)

    elif kind == "healthy":
        n_points = int(round(300.0 / STEP_S)) + 1
        t_s = np.round(np.linspace(0.0, 300.0, n_points), 3)

        mem_base = float(rng.uniform(0.35, 0.65))
        mem_noise_std = float(rng.uniform(0.01, 0.03))
        mem_noise = rng.normal(0.0, mem_noise_std, size=n_points)
        mem_frac = np.clip(mem_base + mem_noise, 0.0, 0.95)

        cpu, err = _normal_cpu_and_err(n_points, rng)
        fail_t = None

    elif kind == "spike":
        n_points = int(round(300.0 / STEP_S)) + 1
        t_s = np.round(np.linspace(0.0, 300.0, n_points), 3)

        mem_base = float(rng.uniform(0.35, 0.65))
        mem_noise_std = float(rng.uniform(0.01, 0.03))
        mem_noise = rng.normal(0.0, mem_noise_std, size=n_points)

        raw_amp = float(rng.uniform(0.20, 0.35))
        bump_dur = float(rng.uniform(4.0, 12.0))
        bump_start = float(rng.uniform(40.0, 250.0))
        bump_end = bump_start + bump_dur

        max_amp = max(0.05, 0.88 - mem_base)
        bump_amp = min(raw_amp, max_amp)

        bump = np.zeros(n_points)
        mask = (t_s >= bump_start) & (t_s <= bump_end)
        if np.any(mask):
            phase = (t_s[mask] - bump_start) / bump_dur
            bump[mask] = bump_amp * (np.sin(np.pi * phase) ** 2)

        mem_frac = np.clip(mem_base + mem_noise + bump, 0.0, 0.895)

        cpu, err = _normal_cpu_and_err(n_points, rng)

        cpu_bump_flag = float(rng.uniform(0.0, 1.0)) < 0.5
        if cpu_bump_flag:
            cpu_bump_amp = float(rng.uniform(30.0, 45.0))
            cpu_bump = np.zeros(n_points)
            if np.any(mask):
                phase = (t_s[mask] - bump_start) / bump_dur
                cpu_bump[mask] = cpu_bump_amp * (np.sin(np.pi * phase) ** 2)
            cpu = np.clip(cpu + cpu_bump, 0.0, 100.0)

        fail_t = None

    elif kind == "sawtooth":
        n_points = int(round(300.0 / STEP_S)) + 1
        t_s = np.round(np.linspace(0.0, 300.0, n_points), 3)

        trend = np.zeros(n_points)
        curr_idx = 0
        while curr_idx < n_points:
            peak = float(rng.uniform(0.75, 0.85))
            ramp_s = float(rng.uniform(40.0, 70.0))
            ramp_steps = max(1, int(round(ramp_s / STEP_S)))
            end_idx = min(n_points, curr_idx + ramp_steps)
            steps_in_cycle = end_idx - curr_idx
            cycle_fracs = 0.30 + (peak - 0.30) * np.linspace(
                0.0, 1.0, ramp_steps
            )[:steps_in_cycle]
            trend[curr_idx:end_idx] = cycle_fracs
            curr_idx = end_idx

        noise = rng.normal(0.0, 0.01, size=n_points)
        mem_frac = np.clip(trend + noise, 0.0, 0.95)

        cpu, err = _normal_cpu_and_err(n_points, rng)
        fail_t = None

    points = [
        {
            "t_s": round(float(t_s[i]), 3),
            "mem_mb": round(float(mem_frac[i] * limit_mb), 3),
            "mem_limit_mb": round(float(limit_mb), 3),
            "cpu_pct": round(float(cpu[i]), 3),
            "restarts": 0,
            "err_pct": round(float(err[i]), 3),
        }
        for i in range(len(t_s))
    ]

    return points, fail_t
