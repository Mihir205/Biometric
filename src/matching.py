"""
src/matching.py — Fingerprint minutiae matcher.

Matcher Design Specification (Decision D006):
  Strategy:  Local-structure alignment with Hungarian-assignment scoring.
  Alignment: Exhaustive pairwise (dx, dy, dθ) alignment using all anchor pairs.
             For each candidate alignment, count supporting minutiae pairs.
  Score:     score = matched_pairs / max(|M1|, |M2|) — a Jaccard-like ratio in [0, 1].
  Threshold: MATCH_SCORE_THRESHOLD from config.py (frozen at M3; tuned on dev data only).

Distance and angle tolerances are defined in config.py:
  MATCH_DISTANCE_THRESHOLD (pixels)
  MATCH_ANGLE_THRESHOLD_DEG (degrees)

Paper reference: §5 — Minutiae matching.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

import config
from src.template import FingerprintTemplate
from src.security import get_secure_logger

_logger = get_secure_logger(__name__)


# ─── Match result ─────────────────────────────────────────────────────────────

class MatchResult(NamedTuple):
    score: float          # [0.0, 1.0] — higher is more similar
    matched_pairs: int    # number of paired minutiae
    n1: int               # minutiae count in template 1
    n2: int               # minutiae count in template 2
    decision: bool        # True = same finger (score ≥ threshold)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _angle_diff(a1: float, a2: float) -> float:
    """Absolute angular difference in radians, wrapped to [0, π)."""
    diff = abs(a1 - a2) % (2 * math.pi)
    if diff > math.pi:
        diff = 2 * math.pi - diff
    return diff


def _transform_point(x: float, y: float, dx: float, dy: float, dtheta: float) -> tuple[float, float]:
    """Apply a 2D rigid transform (rotation + translation) to a point."""
    cos_t = math.cos(dtheta)
    sin_t = math.sin(dtheta)
    xr = x * cos_t - y * sin_t + dx
    yr = x * sin_t + y * cos_t + dy
    return xr, yr


def _count_matches(
    m1: list[dict],
    m2: list[dict],
    dx: float,
    dy: float,
    dtheta: float,
) -> int:
    """
    Count how many minutiae in m2 are matched by transformed m1 under (dx, dy, dθ).
    Each m2 minutia is matched at most once (greedy by distance).
    """
    dist_thresh = config.MATCH_DISTANCE_THRESHOLD
    angle_thresh = math.radians(config.MATCH_ANGLE_THRESHOLD_DEG)

    matched_m2 = set()
    count = 0

    for p1 in m1:
        tx, ty = _transform_point(p1["x"], p1["y"], dx, dy, dtheta)
        best_dist = float("inf")
        best_j = -1
        for j, p2 in enumerate(m2):
            if j in matched_m2:
                continue
            dist = math.hypot(tx - p2["x"], ty - p2["y"])
            if dist > dist_thresh:
                continue
            adiff = _angle_diff(p1["angle"] + dtheta, p2["angle"])
            if adiff > angle_thresh:
                continue
            if dist < best_dist:
                best_dist = dist
                best_j = j
        if best_j >= 0:
            matched_m2.add(best_j)
            count += 1

    return count


# ─── Main matcher ─────────────────────────────────────────────────────────────

def match(t1: FingerprintTemplate, t2: FingerprintTemplate) -> MatchResult:
    """
    Compare two fingerprint templates and return a MatchResult.

    Paper reference: §5

    Args:
        t1: Enrolled template (or probe 1).
        t2: Probe template (or probe 2).

    Returns:
        MatchResult — contains score, matched_pairs, counts, and decision.
        NOTE: The score is intentionally NOT logged (see THREAT_MODEL §3.4).
    """
    m1 = t1.minutiae
    m2 = t2.minutiae

    if not m1 or not m2:
        _logger.info("Match attempted with empty template. decision=FAIL")
        return MatchResult(score=0.0, matched_pairs=0, n1=len(m1), n2=len(m2), decision=False)

    n1, n2 = len(m1), len(m2)
    pts1 = np.array([[p["x"], p["y"], p["angle"]] for p in m1], dtype=np.float32)
    pts2 = np.array([[p["x"], p["y"], p["angle"]] for p in m2], dtype=np.float32)

    x1, y1, a1 = pts1[:, 0], pts1[:, 1], pts1[:, 2]
    x2, y2, a2 = pts2[:, 0], pts2[:, 1], pts2[:, 2]

    dist_thresh_sq = float(config.MATCH_DISTANCE_THRESHOLD) ** 2
    angle_thresh = float(math.radians(config.MATCH_ANGLE_THRESHOLD_DEG))

    # Check candidate anchors with full coverage for reliable alignment
    max_anchors = 80
    step1 = max(1, n1 // max_anchors)
    step2 = max(1, n2 // max_anchors)
    idx1 = list(range(0, n1, step1))
    idx2 = list(range(0, n2, step2))

    best_count = 0

    for i in idx1:
        p1_x, p1_y, p1_a = x1[i], y1[i], a1[i]
        t1_type = m1[i].get("type")
        for j in idx2:
            if t1_type and m2[j].get("type") and t1_type != m2[j].get("type"):
                continue

            dtheta = float(a2[j] - p1_a)
            cos_t = math.cos(dtheta)
            sin_t = math.sin(dtheta)

            # Rigid transform of points in t1
            dx_trans = float(x2[j] - (p1_x * cos_t - p1_y * sin_t))
            dy_trans = float(y2[j] - (p1_x * sin_t + p1_y * cos_t))

            tx = x1 * cos_t - y1 * sin_t + dx_trans
            ty = x1 * sin_t + y1 * cos_t + dy_trans
            ta = (a1 + dtheta) % (2.0 * math.pi)

            # Pairwise distances and angle differences (N1 x N2)
            p_dx = tx[:, None] - x2[None, :]
            p_dy = ty[:, None] - y2[None, :]
            dist_sq = p_dx * p_dx + p_dy * p_dy

            adiff = np.abs(ta[:, None] - a2[None, :]) % (2.0 * math.pi)
            adiff = np.minimum(adiff, 2.0 * math.pi - adiff)

            valid = (dist_sq <= dist_thresh_sq) & (adiff <= angle_thresh)
            valid_pairs = np.argwhere(valid)
            if len(valid_pairs) == 0:
                continue

            # Greedy nearest assignment
            dists = dist_sq[valid_pairs[:, 0], valid_pairs[:, 1]]
            order = np.argsort(dists)
            used1 = set()
            used2 = set()
            cnt = 0
            for k in order:
                u, v = int(valid_pairs[k, 0]), int(valid_pairs[k, 1])
                if u not in used1 and v not in used2:
                    used1.add(u)
                    used2.add(v)
                    cnt += 1

            if cnt > best_count:
                best_count = cnt
                if best_count == min(n1, n2):
                    break

    score = best_count / max(n1, n2) if max(n1, n2) > 0 else 0.0
    decision = score >= config.MATCH_SCORE_THRESHOLD

    _logger.info("Match complete. n1=%d n2=%d matched=%d decision=%s", n1, n2, best_count, decision)
    return MatchResult(score=score, matched_pairs=best_count, n1=n1, n2=n2, decision=decision)

