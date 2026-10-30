"""
tests/test_minutiae.py — Unit tests for minutiae extraction.

Tests:
  - Cross-number on hand-built skeletons (known ridge endings and bifurcations)
  - Border exclusion: minutiae near edges are dropped
  - Spurious removal: short ridge endings are removed
  - Empty skeleton: returns empty list
"""

from __future__ import annotations

import numpy as np
import pytest

from src.minutiae_extraction import Minutia, extract, remove_spurious


def _empty_orientation(h: int, w: int) -> np.ndarray:
    return np.zeros((h, w), dtype=np.float32)


def _full_mask(h: int, w: int) -> np.ndarray:
    return np.ones((h, w), dtype=bool)


# ─── Cross-number on synthetic skeletons ──────────────────────────────────────

def test_single_ending_detected():
    """A single horizontal line has two ridge endings at its tips."""
    skel = np.zeros((100, 100), dtype=bool)
    skel[50, 20:80] = True  # horizontal ridge
    orient = _empty_orientation(100, 100)
    mask = _full_mask(100, 100)
    minutiae = extract(skel, orient, mask)
    endings = [m for m in minutiae if m.mtype == "ending"]
    assert len(endings) >= 2, f"Expected ≥2 endings, got {len(endings)}"


def test_t_junction_bifurcation():
    """A T-junction in the skeleton should yield a bifurcation."""
    skel = np.zeros((100, 100), dtype=bool)
    skel[50, 20:80] = True   # horizontal ridge
    skel[20:50, 50] = True   # vertical branch
    orient = _empty_orientation(100, 100)
    mask = _full_mask(100, 100)
    minutiae = extract(skel, orient, mask)
    bifurcations = [m for m in minutiae if m.mtype == "bifurcation"]
    assert len(bifurcations) >= 1, f"Expected ≥1 bifurcation, got {len(bifurcations)}"


def test_empty_skeleton():
    skel = np.zeros((100, 100), dtype=bool)
    orient = _empty_orientation(100, 100)
    mask = _full_mask(100, 100)
    minutiae = extract(skel, orient, mask)
    assert minutiae == []


# ─── Border exclusion ─────────────────────────────────────────────────────────

def test_border_minutiae_excluded():
    """A ridge ending within the border margin must be excluded."""
    import config
    margin = config.MINUTIAE_BORDER_MARGIN
    skel = np.zeros((100, 100), dtype=bool)
    # Place a short ridge near the border
    skel[3, 3:8] = True  # within margin from top-left corner
    orient = _empty_orientation(100, 100)
    mask = _full_mask(100, 100)
    minutiae = extract(skel, orient, mask)
    for m in minutiae:
        assert m.x >= margin and m.y >= margin, \
            f"Minutia at ({m.x},{m.y}) is within border margin {margin}"


# ─── Spurious removal ─────────────────────────────────────────────────────────

def test_short_ridge_removed():
    """A very short ridge ending (< MIN_RIDGE_LEN) should be removed by spurious filter."""
    import config
    skel = np.zeros((100, 100), dtype=bool)
    # Short ridge (length = 3, below default MIN_RIDGE_LEN = 10)
    skel[50, 40:43] = True
    orient = _empty_orientation(100, 100)
    mask = _full_mask(100, 100)
    raw = extract(skel, orient, mask)
    filtered = remove_spurious(raw, skel)
    assert len(filtered) == 0, \
        f"Short ridge endings should be removed; got {len(filtered)} minutiae"


def test_long_ridge_kept():
    """A long ridge ending (≥ MIN_RIDGE_LEN) should survive the spurious filter."""
    import config
    skel = np.zeros((100, 100), dtype=bool)
    skel[50, 20:60] = True  # length = 40, well above threshold
    orient = _empty_orientation(100, 100)
    mask = _full_mask(100, 100)
    raw = extract(skel, orient, mask)
    filtered = remove_spurious(raw, skel)
    endings = [m for m in filtered if m.mtype == "ending"]
    assert len(endings) >= 1, "Long ridge endings should survive spurious filter"
