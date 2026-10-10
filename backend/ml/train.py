"""
backend/ml/train.py
TASK P3 — Train, evaluate, and threshold-tune failure prediction model.

CLI:
    python -m backend.ml.train [--data backend/ml/data.csv] [--seed 7] [--eval-only] [--out-model backend/ml/model.joblib]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from backend.ml.config import FEATURES, PERSISTENCE

FAILING_KINDS = {"slow_leak", "fast_leak", "cpu_sat"}
HARMLESS_KINDS = {"healthy", "spike", "sawtooth"}


def episodes(
    test_df: pd.DataFrame,
    thr: float,
    persistence: int = PERSISTENCE,
) -> List[Tuple[str, str, Optional[float], Optional[float]]]:
    """Evaluates alarm events per episode (run_id).

    For each test run_id ordered by t_end, alarm = first t_end where probability >= thr
    for PERSISTENCE consecutive scored windows in a row.

    Yields/returns:
        (run_id, kind, alarm, fail_t)
    """
    results: List[Tuple[str, str, Optional[float], Optional[float]]] = []

    # Group by run_id; runs retain deterministic sequence
    for run_id, group in test_df.groupby("run_id", sort=False):
        group_sorted = group.sort_values("t_end")
        kind = str(group_sorted["kind"].iloc[0])
        raw_fail_t = group_sorted["fail_t"].iloc[0]
        fail_t = float(raw_fail_t) if pd.notna(raw_fail_t) else None

        probs = group_sorted["prob"].values
        t_ends = group_sorted["t_end"].values

        alarm: Optional[float] = None
        streak = 0
        for prob_val, t_val in zip(probs, t_ends):
            if prob_val >= thr:
                streak += 1
                if streak >= persistence:
                    alarm = float(t_val)
                    break
            else:
                streak = 0

        results.append((str(run_id), kind, alarm, fail_t))

    return results


def run_threshold_sweep(
    test_df: pd.DataFrame,
    persistence: int = PERSISTENCE,
) -> Tuple[List[Dict[str, Any]], float]:
    """Sweeps threshold from 0.50 to 0.99 (step 0.01) and selects the suggested threshold."""
    sweep_results: List[Dict[str, Any]] = []
    thresholds = [round(0.50 + i * 0.01, 2) for i in range(50)]

    suggested_threshold: Optional[float] = None

    for thr in thresholds:
        ep_list = episodes(test_df, thr, persistence=persistence)

        failing_eps = [e for e in ep_list if e[1] in FAILING_KINDS]
        harmless_eps = [e for e in ep_list if e[1] in HARMLESS_KINDS]

        # Failing runs caught before fail_t
        caught_runs = [
            e for e in failing_eps
            if e[2] is not None and e[3] is not None and e[2] < e[3]
        ]
        caught_pct = len(caught_runs) / len(failing_eps) if failing_eps else 0.0

        lead_times = [
            (e[3] - e[2]) for e in caught_runs
            if e[2] is not None and e[3] is not None
        ]
        median_warning_s = float(np.median(lead_times)) if lead_times else 0.0

        # False alarms on harmless runs
        harmless_alarms = [e for e in harmless_eps if e[2] is not None]
        false_alarm_rate = len(harmless_alarms) / len(harmless_eps) if harmless_eps else 0.0

        # Breakdown by harmless kind
        by_kind_far: Dict[str, float] = {}
        for k in HARMLESS_KINDS:
            k_eps = [e for e in harmless_eps if e[1] == k]
            k_alarms = [e for e in k_eps if e[2] is not None]
            by_kind_far[f"{k}_far"] = len(k_alarms) / len(k_eps) if k_eps else 0.0

        entry = {
            "thr": thr,
            "caught_pct": round(caught_pct, 4),
            "false_alarm_rate": round(false_alarm_rate, 4),
            "median_warning_s": round(median_warning_s, 2),
            "healthy_far": round(by_kind_far.get("healthy_far", 0.0), 4),
            "spike_far": round(by_kind_far.get("spike_far", 0.0), 4),
            "sawtooth_far": round(by_kind_far.get("sawtooth_far", 0.0), 4),
            "total_failing": len(failing_eps),
            "caught_count": len(caught_runs),
            "total_harmless": len(harmless_eps),
            "false_alarm_count": len(harmless_alarms),
        }
        sweep_results.append(entry)

        # Suggested threshold: lowest threshold whose false-alarm rate on healthy, spike, sawtooth is <= 2%
        if suggested_threshold is None and false_alarm_rate <= 0.02:
            suggested_threshold = thr

    if suggested_threshold is None:
        # Fallback to threshold with lowest FAR
        suggested_threshold = min(sweep_results, key=lambda x: x["false_alarm_rate"])["thr"]

    return sweep_results, suggested_threshold


def train_and_evaluate(
    data_path: str = "backend/ml/data.csv",
    seed: int = 7,
    eval_only: bool = False,
    out_model_path: str = "backend/ml/model.joblib",
) -> Dict[str, Any]:
    """Loads dataset, trains pipeline (or loads model), evaluates episodes and saves reports."""
    data_file = Path(data_path)
    if not data_file.exists():
        raise FileNotFoundError(f"Training data not found at {data_file}")

    print(f"Loading dataset from {data_file}...")
    df = pd.read_csv(data_file)

    # 1. GroupShuffleSplit by run_id
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    train_idx, test_idx = next(gss.split(df, groups=df["run_id"]))

    # 2. Training set subsampled: train = df.iloc[tr].iloc[::3]
    train_df = df.iloc[train_idx].iloc[::3].copy()
    test_df = df.iloc[test_idx].copy()

    print(f"Split: {len(train_df)} train windows (subsampled 1/3) | {len(test_df)} test windows")

    # 3. Model pipeline
    model_file = Path(out_model_path)
    model: Pipeline

    if eval_only and model_file.exists():
        print(f"Loading existing model from {model_file} (--eval-only)...")
        model = joblib.load(model_file)
    else:
        print("Training LogisticRegression pipeline...")
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed),
        )
        model.fit(train_df[FEATURES], train_df["label"])

        model_file.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_file)
        model_size_kb = model_file.stat().st_size / 1024.0
        print(f"Model saved to {model_file} ({model_size_kb:.2f} KB, target < 1024 KB)")

    # 4. Predict probabilities on test set
    test_df["prob"] = model.predict_proba(test_df[FEATURES])[:, 1]

    # 5. Threshold sweep and episode evaluation
    sweep_results, suggested_thr = run_threshold_sweep(test_df, persistence=PERSISTENCE)

    # Extract metrics at suggested threshold
    suggested_stats = next(s for s in sweep_results if s["thr"] == suggested_thr)

    # Window-level metrics at suggested threshold
    test_preds = (test_df["prob"] >= suggested_thr).astype(int)
    cm = confusion_matrix(test_df["label"], test_preds).tolist()
    prec = float(precision_score(test_df["label"], test_preds, zero_division=0))
    rec = float(recall_score(test_df["label"], test_preds, zero_division=0))
    f1 = float(f1_score(test_df["label"], test_preds, zero_division=0))

    # Feature coefficients
    clf: LogisticRegression = model.named_steps["logisticregression"]
    raw_coefs = clf.coef_[0]
    intercept = float(clf.intercept_[0])
    feature_coefs = {feat: float(c) for feat, c in zip(FEATURES, raw_coefs)}

    # Breakdown by run kind at suggested threshold
    ep_at_sugg = episodes(test_df, suggested_thr, persistence=PERSISTENCE)
    kind_breakdown: Dict[str, Dict[str, Any]] = {}
    for k in sorted(list(FAILING_KINDS | HARMLESS_KINDS)):
        k_eps = [e for e in ep_at_sugg if e[1] == k]
        total_k = len(k_eps)
        alarm_k = sum(1 for e in k_eps if e[2] is not None)
        caught_k = sum(1 for e in k_eps if e[2] is not None and e[3] is not None and e[2] < e[3])
        kind_breakdown[k] = {
            "total_runs": total_k,
            "alarms": alarm_k,
            "alarm_pct": round(alarm_k / total_k, 4) if total_k else 0.0,
            "caught_pct": round(caught_k / total_k, 4) if total_k and k in FAILING_KINDS else None,
        }

    report_data = {
        "suggested_threshold": suggested_thr,
        "metrics_at_suggested": suggested_stats,
        "window_metrics": {
            "confusion_matrix": cm,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        },
        "by_kind": kind_breakdown,
        "feature_coefficients": feature_coefs,
        "intercept": round(intercept, 4),
        "threshold_sweep": sweep_results,
    }

    # Save backend/ml/report.json
    out_dir = model_file.parent
    report_json_path = out_dir / "report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"Report JSON saved to {report_json_path}")

    # Save backend/ml/report.md
    report_md_path = out_dir / "report.md"
    _generate_markdown_report(report_md_path, report_data)
    print(f"Report Markdown saved to {report_md_path}")

    # Print summary to terminal
    print("\n" + "=" * 70)
    print("AGNITIA ML PREDICTIVE FAILURE DETECTOR - TRAINING SUMMARY")
    print("=" * 70)
    print(f"Suggested Threshold:     {suggested_thr:.2f}")
    print(f"Caught %:                {suggested_stats['caught_pct'] * 100:.1f}%  (target >= 90.0%)")
    print(f"False Alarm %:           {suggested_stats['false_alarm_rate'] * 100:.1f}%  (target <= 2.0%)")
    print(f"Median Warning Seconds:  {suggested_stats['median_warning_s']:.1f}s  (target >= 40.0s)")
    print("=" * 70 + "\n")

    return report_data


def _generate_markdown_report(path: Path, data: Dict[str, Any]) -> None:
    """Writes a readable summary markdown table of metrics and top feature weights."""
    stats = data["metrics_at_suggested"]
    sugg_thr = data["suggested_threshold"]
    coefs = data["feature_coefficients"]
    sorted_coefs = sorted(coefs.items(), key=lambda x: abs(x[1]), reverse=True)

    lines = [
        "# Agnitia Predictive Failure Detector — Model Evaluation Report",
        "",
        "## 1. Executive Summary",
        "",
        f"- **Suggested Threshold**: `{sugg_thr:.2f}`",
        f"- **Failure Detection Rate (Caught %)**: **{stats['caught_pct'] * 100:.1f}%** (Target: ≥ 90.0%)",
        f"- **Harmless False Alarm Rate**: **{stats['false_alarm_rate'] * 100:.1f}%** (Target: ≤ 2.0%)",
        f"- **Median Warning Lead Time**: **{stats['median_warning_s']:.1f} seconds** (Target: ≥ 40.0s)",
        f"- **Window-level Precision**: `{data['window_metrics']['precision'] * 100:.1f}%`",
        f"- **Window-level Recall**: `{data['window_metrics']['recall'] * 100:.1f}%`",
        "",
        "## 2. Performance by Scenario Kind",
        "",
        "| Run Kind | Category | Total Runs | Alarms Triggered | Rate (%) |",
        "|---|---|---|---|---|",
    ]

    for k, v in data["by_kind"].items():
        cat = "Failing" if k in FAILING_KINDS else "Harmless"
        rate = (v["caught_pct"] if cat == "Failing" else v["alarm_pct"]) * 100.0
        lines.append(f"| `{k}` | {cat} | {v['total_runs']} | {v['alarms']} | {rate:.1f}% |")

    lines.extend([
        "",
        "## 3. Top Feature Weights (Logistic Regression Coefficients)",
        "",
        "| Rank | Feature | Coefficient | Interpretation |",
        "|---|---|---|---|",
    ])

    for rank, (feat, weight) in enumerate(sorted_coefs, start=1):
        sign = "+" if weight > 0 else "-"
        direction = "Increases failure risk" if weight > 0 else "Decreases failure risk / baseline"
        lines.append(f"| {rank} | `{feat}` | `{sign}{abs(weight):.4f}` | {direction} |")

    lines.extend([
        "",
        "## 4. Threshold Sweep Sample (Threshold vs. Caught % vs. False Alarm %)",
        "",
        "| Threshold | Caught % | False Alarm % | Healthy FAR | Spike FAR | Sawtooth FAR | Median Warning (s) |",
        "|---|---|---|---|---|---|---|",
    ])

    # Show a sampling around the sweep
    sweep = data["threshold_sweep"]
    for row in sweep[::5]:
        marker = " **(selected)**" if row["thr"] == sugg_thr else ""
        lines.append(
            f"| `{row['thr']:.2f}`{marker} | {row['caught_pct']*100:.1f}% | "
            f"{row['false_alarm_rate']*100:.1f}% | {row['healthy_far']*100:.1f}% | "
            f"{row['spike_far']*100:.1f}% | {row['sawtooth_far']*100:.1f}% | {row['median_warning_s']:.1f}s |"
        )

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate Agnitia failure detector.")
    parser.add_argument("--data", type=str, default="backend/ml/data.csv", help="Path to data CSV")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument("--eval-only", action="store_true", help="Evaluate existing model without retraining")
    parser.add_argument("--out-model", type=str, default="backend/ml/model.joblib", help="Output model path")

    args = parser.parse_args()
    train_and_evaluate(
        data_path=args.data,
        seed=args.seed,
        eval_only=args.eval_only,
        out_model_path=args.out_model,
    )


if __name__ == "__main__":
    main()
