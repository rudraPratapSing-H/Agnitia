# Agnitia Predictive Failure Detector — Model Evaluation Report

## 1. Executive Summary

- **Suggested Threshold**: `0.83`
- **Failure Detection Rate (Caught %)**: **98.0%** (Target: ≥ 90.0%)
- **Harmless False Alarm Rate**: **2.0%** (Target: ≤ 2.0%)
- **Median Warning Lead Time**: **67.0 seconds** (Target: ≥ 40.0s)
- **Window-level Precision**: `88.7%`
- **Window-level Recall**: `85.4%`

## 2. Performance by Scenario Kind

| Run Kind | Category | Total Runs | Alarms Triggered | Rate (%) |
|---|---|---|---|---|
| `cpu_sat` | Failing | 9 | 8 | 88.9% |
| `fast_leak` | Failing | 10 | 10 | 100.0% |
| `healthy` | Harmless | 63 | 0 | 0.0% |
| `sawtooth` | Harmless | 18 | 2 | 11.1% |
| `slow_leak` | Failing | 31 | 31 | 100.0% |
| `spike` | Harmless | 19 | 0 | 0.0% |

## 3. Top Feature Weights (Logistic Regression Coefficients)

| Rank | Feature | Coefficient | Interpretation |
|---|---|---|---|
| 1 | `mem_volatility` | `-10.5397` | Decreases failure risk / baseline |
| 2 | `mem_slope` | `+8.3240` | Increases failure risk |
| 3 | `mem_frac` | `+3.3754` | Increases failure risk |
| 4 | `err_change` | `+1.9712` | Increases failure risk |
| 5 | `mem_accel` | `-0.6305` | Decreases failure risk / baseline |
| 6 | `cpu_frac` | `+0.0422` | Increases failure risk |
| 7 | `restarts` | `-0.0000` | Decreases failure risk / baseline |

## 4. Threshold Sweep Sample (Threshold vs. Caught % vs. False Alarm %)

| Threshold | Caught % | False Alarm % | Healthy FAR | Spike FAR | Sawtooth FAR | Median Warning (s) |
|---|---|---|---|---|---|---|
| `0.50` | 100.0% | 18.0% | 0.0% | 0.0% | 100.0% | 80.0s |
| `0.55` | 100.0% | 17.0% | 0.0% | 0.0% | 94.4% | 80.0s |
| `0.60` | 100.0% | 17.0% | 0.0% | 0.0% | 94.4% | 78.5s |
| `0.65` | 100.0% | 17.0% | 0.0% | 0.0% | 94.4% | 77.0s |
| `0.70` | 100.0% | 14.0% | 0.0% | 0.0% | 77.8% | 74.8s |
| `0.75` | 100.0% | 12.0% | 0.0% | 0.0% | 66.7% | 70.8s |
| `0.80` | 100.0% | 6.0% | 0.0% | 0.0% | 33.3% | 66.2s |
| `0.85` | 98.0% | 0.0% | 0.0% | 0.0% | 0.0% | 61.5s |
| `0.90` | 98.0% | 0.0% | 0.0% | 0.0% | 0.0% | 59.0s |
| `0.95` | 98.0% | 0.0% | 0.0% | 0.0% | 0.0% | 48.0s |
