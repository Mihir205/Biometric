"""
src/segmentation.py — Foreground mask estimation and ridge skeletonisation.

Paper reference: §3.4 — Segmentation; §3.5 — Skeletonisation.

Steps:
  1. Divide the enhanced image into blocks.
  2. Compute block variance; blocks below the threshold are background.
  3. Apply morphological closing to smooth the mask.
  4. Skeletonise the masked foreground using scikit-image.
"""

from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize

import config
from src.security import get_secure_logger

_logger = get_secure_logger(__name__)


def segment(image: np.ndarray) -> np.ndarray:
    """
    Compute a binary foreground mask using block variance.

    Paper reference: §3.4

    Args:
        image: Enhanced float32 image (H, W) in [0, 1].

    Returns:
        Boolean mask (H, W) — True = foreground ridge area.
    """
    h, w = image.shape
    block = config.SEGMENT_BLOCK_SIZE
    threshold = config.SEGMENT_VAR_THRESHOLD / (255.0 ** 2)  # normalise to float range

    mask = np.zeros((h, w), dtype=bool)

    for y in range(0, h, block):
        for x in range(0, w, block):
            patch = image[y: y + block, x: x + block]
            if patch.var() > threshold:
                mask[y: y + block, x: x + block] = True

    # Morphological closing to fill small holes in the mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (block, block))
    mask_uint8 = mask.astype(np.uint8) * 255
    mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel)
    mask = mask_uint8 > 0

    _logger.info("Segmentation complete. foreground_fraction=%.2f", mask.mean())
    return mask


def skeletonise(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Binarise and skeletonise the enhanced fingerprint image within the foreground mask.

    Paper reference: §3.5

    Args:
        image: Enhanced float32 image (H, W) in [0, 1].
        mask:  Foreground boolean mask (H, W).

    Returns:
        Boolean skeleton array (H, W) — True = ridge pixel.
    """
    # Binarise: ridges are dark in the enhanced image (after Gabor)
    # Otsu threshold on the masked region
    masked = (image * mask.astype(np.float32) * 255).astype(np.uint8)
    _, binary = cv2.threshold(masked, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    binary_bool = (binary > 0) & mask

    skeleton = skeletonize(binary_bool)
    _logger.info("Skeletonisation complete. skeleton_pixels=%d", skeleton.sum())
    return skeleton
