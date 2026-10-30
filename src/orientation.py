"""
src/orientation.py — Gradient-based orientation field estimation.

Paper reference: §3.2 — Ridge orientation estimation.

Algorithm:
  1. Compute image gradients (Gx, Gy) using Sobel operators.
  2. Compute squared gradients and cross-product per block.
  3. Use double-angle formula to estimate dominant ridge orientation per block.
  4. Apply Gaussian smoothing to the orientation field.
  5. Upsample to per-pixel resolution.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter

import config
from src.security import get_secure_logger

_logger = get_secure_logger(__name__)


def estimate(image: np.ndarray) -> np.ndarray:
    """
    Estimate the per-pixel ridge orientation field.

    Paper reference: §3.2

    Args:
        image: Normalised float32 grayscale image (H, W) in [0, 1].

    Returns:
        Orientation field as float32 array (H, W) with angles in [0, π).
        Each value is the dominant ridge direction at that pixel.
    """
    h, w = image.shape
    block = config.ORIENTATION_BLOCK_SIZE
    img = (image * 255).astype(np.float32)

    # Sobel gradients
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)

    # Number of blocks
    num_blocks_y = (h + block - 1) // block
    num_blocks_x = (w + block - 1) // block

    # Per-block orientation (double-angle formula)
    block_orient = np.zeros((num_blocks_y, num_blocks_x), dtype=np.float32)

    for by in range(num_blocks_y):
        for bx in range(num_blocks_x):
            y0, y1 = by * block, min((by + 1) * block, h)
            x0, x1 = bx * block, min((bx + 1) * block, w)
            gx_b = gx[y0:y1, x0:x1]
            gy_b = gy[y0:y1, x0:x1]
            vx = 2.0 * (gx_b * gy_b).sum()
            vy = (gx_b ** 2 - gy_b ** 2).sum()
            # Dominant orientation angle (in [0, pi))
            block_orient[by, bx] = 0.5 * (np.arctan2(vx, vy) + np.pi)

    # Smooth orientation field (convert to vector, smooth, convert back)
    cos2 = np.cos(2.0 * block_orient)
    sin2 = np.sin(2.0 * block_orient)
    sigma = config.ORIENTATION_SMOOTH_SIGMA / block
    cos2_s = gaussian_filter(cos2, sigma=sigma)
    sin2_s = gaussian_filter(sin2, sigma=sigma)
    smoothed = 0.5 * (np.arctan2(sin2_s, cos2_s) + np.pi)

    # Upsample block-level orientation to per-pixel
    orientation_field = cv2.resize(
        smoothed,
        (w, h),
        interpolation=cv2.INTER_LINEAR,
    )

    _logger.info("Orientation field estimated. shape=%s blocks=%dx%d", image.shape, num_blocks_y, num_blocks_x)
    return orientation_field.astype(np.float32)
