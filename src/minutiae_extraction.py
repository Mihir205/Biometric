"""
src/minutiae_extraction.py — Cross-number minutiae extraction and spurious removal.

Paper reference: §4 — Minutiae extraction using crossing number.

Crossing number (CN) algorithm:
  For each skeleton pixel P with value 1, CN = 0.5 * Σ|P(i) - P(i-1)|
  over the 8 connected neighbours (i=1..8, cyclic).
    CN == 1 → ridge ending
    CN == 3 → ridge bifurcation

Spurious minutiae removal:
  - Border exclusion: remove minutiae within MINUTIAE_BORDER_MARGIN pixels of image edge.
  - Short ridge pruning: remove ridge endings connected to branches shorter than MINUTIAE_MIN_RIDGE_LEN.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

import config
from src.security import get_secure_logger

_logger = get_secure_logger(__name__)


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class Minutia:
    x: int          # column (pixel)
    y: int          # row (pixel)
    angle: float    # ridge direction in radians [0, 2π)
    mtype: str      # "ending" | "bifurcation"
    quality: float  # [0.0, 1.0] — reserved for future quality weighting


# ─── Crossing-number extraction ───────────────────────────────────────────────

_NEIGHBOURS = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]


def _crossing_number(skel: np.ndarray, y: int, x: int) -> int:
    """Compute the crossing number for the 8-neighbourhood of pixel (y, x)."""
    neighbours = []
    h, w = skel.shape
    for dy, dx in _NEIGHBOURS:
        ny, nx = y + dy, x + dx
        if 0 <= ny < h and 0 <= nx < w:
            neighbours.append(int(skel[ny, nx]))
        else:
            neighbours.append(0)
    # Wrap-around for cyclic sum
    neighbours.append(neighbours[0])
    cn = sum(abs(neighbours[i] - neighbours[i - 1]) for i in range(1, 9))
    return cn // 2


def _ridge_direction(skel: np.ndarray, y: int, x: int, orientation_field: np.ndarray) -> float:
    """Approximate the local ridge direction from the orientation field."""
    h, w = skel.shape
    # Use local orientation field if available; otherwise fall back to 0
    oy = min(max(y, 0), h - 1)
    ox = min(max(x, 0), w - 1)
    return float(orientation_field[oy, ox])


def extract(
    skeleton: np.ndarray,
    orientation_field: np.ndarray,
    mask: np.ndarray,
) -> list[Minutia]:
    """
    Extract minutiae from the skeleton using the crossing-number method.

    Paper reference: §4.1

    Args:
        skeleton:          Boolean (H, W) — True = ridge pixel.
        orientation_field: Float32 (H, W) — ridge orientation in radians.
        mask:              Boolean (H, W) — foreground region.

    Returns:
        List of Minutia objects (ridge endings and bifurcations).
    """
    h, w = skeleton.shape
    skel_int = skeleton.astype(np.uint8)
    minutiae: list[Minutia] = []
    margin = config.MINUTIAE_BORDER_MARGIN

    ys, xs = np.where(skel_int == 1)
    for y, x in zip(ys, xs):
        # Border exclusion
        if y < margin or y >= h - margin or x < margin or x >= w - margin:
            continue
        # Only process foreground pixels
        if not mask[y, x]:
            continue

        cn = _crossing_number(skel_int, y, x)

        if cn == 1:
            mtype = "ending"
        elif cn == 3:
            mtype = "bifurcation"
        else:
            continue

        angle = _ridge_direction(skel_int, y, x, orientation_field)
        minutiae.append(Minutia(x=x, y=y, angle=angle, mtype=mtype, quality=1.0))

    _logger.info("Raw minutiae count: %d", len(minutiae))
    return minutiae


# ─── Spurious removal ─────────────────────────────────────────────────────────

def remove_spurious(
    minutiae: list[Minutia],
    skeleton: np.ndarray,
) -> list[Minutia]:
    """
    Remove likely-spurious minutiae using short-ridge pruning.

    Any ridge ending connected to a branch shorter than MINUTIAE_MIN_RIDGE_LEN
    pixels is discarded.

    Paper reference: §4.2

    Args:
        minutiae: Raw minutiae list from extract().
        skeleton: Boolean skeleton (H, W).

    Returns:
        Filtered minutiae list.
    """
    min_len = config.MINUTIAE_MIN_RIDGE_LEN
    skel_int = skeleton.astype(np.uint8)

    # Label connected components of the skeleton for branch-length measurement
    num_labels, labels = cv2.connectedComponents(skel_int, connectivity=8)

    # Map label → pixel count (branch length proxy)
    label_sizes = np.bincount(labels.ravel())

    filtered: list[Minutia] = []
    for m in minutiae:
        if m.mtype == "ending":
            label = int(labels[m.y, m.x])
            branch_len = int(label_sizes[label]) if label > 0 else 0
            if branch_len < min_len:
                continue  # discard short spur
        filtered.append(m)

    _logger.info("Minutiae after spurious removal: %d (removed %d)", len(filtered), len(minutiae) - len(filtered))
    return filtered
