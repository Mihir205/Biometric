"""
src/enhancement.py — Gabor-filter fingerprint ridge enhancement.

Paper reference: §3.3 — Image enhancement using oriented Gabor filters.

The enhancement pipeline:
  1. Compute the local orientation field (delegated to orientation.py).
  2. For each block, convolve with a Gabor filter tuned to the local orientation.
  3. Return the enhanced image in [0, 1] float32.
"""

from __future__ import annotations

import cv2
import numpy as np

import config
from src.security import get_secure_logger

_logger = get_secure_logger(__name__)


def _build_gabor_kernel(theta: float) -> np.ndarray:
    """
    Build a Gabor filter kernel for a given orientation angle.

    Args:
        theta: Ridge orientation in radians.

    Returns:
        Gabor kernel as float32 array.
    """
    kw, kh = config.GABOR_KERNEL_SIZE
    return cv2.getGaborKernel(
        ksize=(kw, kh),
        sigma=config.GABOR_SIGMA_X,
        theta=theta,
        lambd=config.GABOR_LAMBDA,
        gamma=config.GABOR_GAMMA,
        psi=0,
        ktype=cv2.CV_32F,
    )


def enhance(image: np.ndarray, orientation_field: np.ndarray) -> np.ndarray:
    """
    Enhance fingerprint ridges using oriented Gabor filters.

    Paper reference: §3.3

    Args:
        image:             Normalised float32 grayscale image (H, W) in [0, 1].
        orientation_field: Per-pixel orientation in radians (H, W), as returned
                           by orientation.estimate().

    Returns:
        Enhanced float32 image (H, W) in [0, 1].
    """
    h, w = image.shape
    img_uint8 = (image * 255).astype(np.uint8)
    enhanced = np.zeros_like(image, dtype=np.float32)
    count_map = np.zeros_like(image, dtype=np.float32)

    # Quantise orientations to NUM_GABOR_ORIENTATIONS discrete angles
    n = config.NUM_GABOR_ORIENTATIONS
    angles = np.linspace(0, np.pi, n, endpoint=False)
    kernels = [_build_gabor_kernel(a) for a in angles]

    # Assign each pixel to the nearest discrete orientation
    q_idx = np.round(orientation_field / np.pi * n).astype(int) % n

    for i, kernel in enumerate(kernels):
        mask = (q_idx == i)
        if not mask.any():
            continue
        filtered = cv2.filter2D(img_uint8, cv2.CV_32F, kernel)
        filtered = np.clip(filtered, 0, 255) / 255.0
        enhanced += filtered * mask.astype(np.float32)
        count_map += mask.astype(np.float32)

    # Avoid division by zero in regions with no assigned orientation
    safe_count = np.where(count_map > 0, count_map, 1.0)
    enhanced /= safe_count
    enhanced = np.clip(enhanced, 0.0, 1.0)

    _logger.info("Enhancement complete. shape=%s", image.shape)
    return enhanced.astype(np.float32)
