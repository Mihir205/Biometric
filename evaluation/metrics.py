"""
evaluation/metrics.py — Biometric evaluation metric calculations.

Computes:
  - FAR  (False Accept Rate)   = FP / (FP + TN) = FP / total_impostor
  - FRR  (False Reject Rate)   = FN / (FN + TP) = FN / total_genuine
  - EER  (Equal Error Rate)    = point where FAR ≈ FRR
  - Bootstrap confidence intervals for FAR, FRR, EER
  - Mean processing time (extraction + comparison)
"""

from __future__ import annotations

import numpy as np
from typing import NamedTuple

import config


class MetricResult(NamedTuple):
    threshold: float
    far: float
    frr: float
    eer: float
    eer_threshold: float
    genuine_count: int
    impostor_count: int
    failed_extractions: int
    far_ci_low: float
    far_ci_high: float
    frr_ci_low: float
    frr_ci_high: float
    mean_extraction_ms: float
    mean_comparison_ms: float


def compute_far_frr(
    genuine_scores: list[float],
    impostor_scores: list[float],
    threshold: float,
) -> tuple[float, float]:
    """Compute FAR and FRR at a given threshold."""
    genuine = np.array(genuine_scores)
    impostor = np.array(impostor_scores)
    frr = float(np.mean(genuine < threshold))   # genuine rejected
    far = float(np.mean(impostor >= threshold))  # impostor accepted
    return far, frr


def find_eer(
    genuine_scores: list[float],
    impostor_scores: list[float],
    n_thresholds: int = 1000,
) -> tuple[float, float]:
    """
    Find the Equal Error Rate and the threshold at which FAR ≈ FRR.

    Returns:
        (eer, eer_threshold)
    """
    all_scores = np.concatenate([genuine_scores, impostor_scores])
    thresholds = np.linspace(all_scores.min(), all_scores.max(), n_thresholds)

    best_diff = float("inf")
    eer = 0.0
    eer_t = thresholds[0]

    for t in thresholds:
        far, frr = compute_far_frr(genuine_scores, impostor_scores, t)
        diff = abs(far - frr)
        if diff < best_diff:
            best_diff = diff
            eer = (far + frr) / 2.0
            eer_t = float(t)

    return eer, eer_t


def bootstrap_ci(
    genuine_scores: list[float],
    impostor_scores: list[float],
    threshold: float,
    n: int = config.EVAL_BOOTSTRAP_ITERATIONS,
    alpha: float = 0.05,
    seed: int = config.EVAL_RANDOM_SEED,
) -> tuple[float, float, float, float]:
    """
    Bootstrap confidence intervals for FAR and FRR.

    Returns:
        (far_low, far_high, frr_low, frr_high) at (1-alpha) confidence level.
    """
    rng = np.random.default_rng(seed)
    gen = np.array(genuine_scores)
    imp = np.array(impostor_scores)

    far_samples = []
    frr_samples = []

    for _ in range(n):
        gen_boot = rng.choice(gen, size=len(gen), replace=True)
        imp_boot = rng.choice(imp, size=len(imp), replace=True)
        far, frr = compute_far_frr(gen_boot.tolist(), imp_boot.tolist(), threshold)
        far_samples.append(far)
        frr_samples.append(frr)

    far_arr = np.array(far_samples)
    frr_arr = np.array(frr_samples)
    lo, hi = alpha / 2 * 100, (1 - alpha / 2) * 100

    return (
        float(np.percentile(far_arr, lo)),
        float(np.percentile(far_arr, hi)),
        float(np.percentile(frr_arr, lo)),
        float(np.percentile(frr_arr, hi)),
    )
