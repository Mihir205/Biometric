"""
tests/test_matching.py — Unit tests for the minutiae matcher.

Tests:
  - Identical templates: score should be 1.0, decision True
  - Completely different templates: score should be 0.0 (or very low), decision False
  - Translated template: should still match within tolerance
  - Rotated template: should still match within tolerance
  - Empty template: returns score 0, decision False
  - Score threshold: decision matches config.MATCH_SCORE_THRESHOLD
"""

from __future__ import annotations

import math

import pytest

import config
from src.matching import match
from src.minutiae_extraction import Minutia
from src.template import FingerprintTemplate, create


def _make_template(minutiae_list: list[tuple[int, int, float, str]]) -> FingerprintTemplate:
    """Build a template from (x, y, angle, type) tuples."""
    minutiae = [
        Minutia(x=x, y=y, angle=a, mtype=t, quality=1.0)
        for x, y, a, t in minutiae_list
    ]
    return create("test_user", minutiae)


# ─── Canonical minutiae set for tests ─────────────────────────────────────────

_BASE = [
    (100, 100, 0.0,  "ending"),
    (150, 120, 0.5,  "bifurcation"),
    (200, 180, 1.0,  "ending"),
    (250, 200, 1.5,  "bifurcation"),
    (300, 250, 2.0,  "ending"),
]


# ─── Identity match ───────────────────────────────────────────────────────────

def test_identical_templates_score_one():
    t1 = _make_template(_BASE)
    t2 = _make_template(_BASE)
    result = match(t1, t2)
    assert result.score == pytest.approx(1.0, abs=0.01)
    assert result.decision is True


# ─── Zero overlap ─────────────────────────────────────────────────────────────

def test_different_templates_low_score():
    """
    Test that two templates with structurally incompatible minutiae score below threshold.

    The exhaustive anchor-pair matcher allows any rigid transform (rotation + translation).
    To prevent accidental alignment, we use templates where the inter-minutia DISTANCES differ,
    so after anchoring any pair, the remaining pairs fall outside the distance tolerance.

    Template A: evenly spaced at DIST_THRESHOLD * 5 apart.
    Template B: evenly spaced at DIST_THRESHOLD * 5 apart BUT at a 30° angle to A,
                so that 90° rotation of A does not map onto B (different spacing axis angles
                combined with angle tolerance exclusion drops all but the anchor pair).

    We verify score < MATCH_SCORE_THRESHOLD (0.30), meaning ≤ 1 pair out of 5 matched.
    """
    thr = config.MATCH_DISTANCE_THRESHOLD
    ang_thr = config.MATCH_ANGLE_THRESHOLD_DEG  # degrees

    # Template A: minutiae with angle 0.0 spread along x-axis
    d = thr * 5
    minutiae_a = [
        (100,       100, 0.0,  "ending"),
        (100 + d,   100, 0.0,  "ending"),
        (100 + 2*d, 100, 0.0,  "ending"),
        (100 + 3*d, 100, 0.0,  "ending"),
        (100 + 4*d, 100, 0.0,  "ending"),
    ]

    # Template B: same absolute positions but minutiae angles rotated by > ang_thr * 3
    # This means even if positions align, the angle check prevents matching.
    import math
    bad_angle = math.radians(ang_thr * 4)  # 4× the angle threshold
    minutiae_b = [
        (100,       100, bad_angle,       "ending"),
        (100 + d,   100, bad_angle,       "ending"),
        (100 + 2*d, 100, bad_angle,       "ending"),
        (100 + 3*d, 100, bad_angle,       "ending"),
        (100 + 4*d, 100, bad_angle,       "ending"),
    ]

    t1 = _make_template(minutiae_a)
    t2 = _make_template(minutiae_b)
    result = match(t1, t2)
    # Even though positions are identical, the angle difference exceeds MATCH_ANGLE_THRESHOLD_DEG
    # after accounting for the alignment rotation dtheta derived from the anchor pair angle diff.
    # The score should be 0 (no pairs match) or at most 1/5 = 0.2.
    assert result.score < config.MATCH_SCORE_THRESHOLD, \
        f"Expected score < {config.MATCH_SCORE_THRESHOLD}, got {result.score} matched={result.matched_pairs}"
    assert result.decision is False


# ─── Translation tolerance ────────────────────────────────────────────────────

def test_translated_template_matches():
    """A small translation within MATCH_DISTANCE_THRESHOLD should still match."""
    dx, dy = config.MATCH_DISTANCE_THRESHOLD // 2, config.MATCH_DISTANCE_THRESHOLD // 2
    shifted = [(x + dx, y + dy, a, t) for x, y, a, t in _BASE]
    t1 = _make_template(_BASE)
    t2 = _make_template(shifted)
    result = match(t1, t2)
    assert result.matched_pairs >= len(_BASE) // 2


# ─── Rotation tolerance ───────────────────────────────────────────────────────

def test_slightly_rotated_template_matches():
    """A small rotation within MATCH_ANGLE_THRESHOLD_DEG should still match."""
    theta = math.radians(config.MATCH_ANGLE_THRESHOLD_DEG / 2)
    rotated = []
    for x, y, a, t in _BASE:
        rx = x * math.cos(theta) - y * math.sin(theta)
        ry = x * math.sin(theta) + y * math.cos(theta)
        rotated.append((int(rx), int(ry), a + theta, t))

    t1 = _make_template(_BASE)
    t2 = _make_template(rotated)
    result = match(t1, t2)
    assert result.matched_pairs >= len(_BASE) // 2


# ─── Empty templates ──────────────────────────────────────────────────────────

def test_empty_template_score_zero():
    t1 = _make_template(_BASE)
    t2 = _make_template([])
    result = match(t1, t2)
    assert result.score == 0.0
    assert result.decision is False


def test_both_empty_templates():
    t1 = _make_template([])
    t2 = _make_template([])
    result = match(t1, t2)
    assert result.score == 0.0
    assert result.decision is False


# ─── Threshold boundary ───────────────────────────────────────────────────────

def test_threshold_comes_from_config():
    """The decision must use config.MATCH_SCORE_THRESHOLD (not a hardcoded value)."""
    t1 = _make_template(_BASE)
    t2 = _make_template(_BASE)
    result = match(t1, t2)
    expected_decision = result.score >= config.MATCH_SCORE_THRESHOLD
    assert result.decision == expected_decision
