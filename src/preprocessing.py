"""
src/preprocessing.py — Input validation, grayscale conversion, and normalisation.

Security-critical module: all external input (file uploads) enters the system here.
Every check must pass before the image reaches any other pipeline stage.

Paper reference: §3.1 — Image normalisation.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import tempfile
from typing import Optional

import cv2
import numpy as np

import config
from src.security import get_secure_logger

_logger = get_secure_logger(__name__)


# ─── Exceptions ───────────────────────────────────────────────────────────────

class InputValidationError(Exception):
    """Raised when an uploaded file fails any input validation check."""


# ─── 1. Input Validation ──────────────────────────────────────────────────────

def _file_hash(data: bytes) -> str:
    """Return a short hex digest for safe logging (never log raw bytes)."""
    return hashlib.sha256(data).hexdigest()[:12]


def _check_extension(path: str | os.PathLike) -> str:
    """Validate file extension against the allowlist. Returns the lowercased extension."""
    ext = pathlib.Path(path).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise InputValidationError(
            f"File extension '{ext}' is not allowed. "
            f"Allowed: {sorted(config.ALLOWED_EXTENSIONS)}"
        )
    return ext


def _check_magic_bytes(data: bytes, ext: str) -> None:
    """Verify the file's magic bytes match its declared extension."""
    if ext not in config.MAGIC_BYTES:
        return  # no magic bytes defined for this extension; extension check is sufficient
    offset, expected = config.MAGIC_BYTES[ext]
    actual = data[offset: offset + len(expected)]
    if actual != expected:
        raise InputValidationError(
            "File magic bytes do not match the declared file extension. "
            "The file may have been renamed or is corrupt."
        )


def _check_file_size(data: bytes) -> None:
    """Reject files that exceed the maximum allowed size."""
    if len(data) == 0:
        raise InputValidationError("File is empty (zero bytes).")
    if len(data) > config.MAX_FILE_SIZE_BYTES:
        raise InputValidationError(
            f"File size {len(data)} bytes exceeds the maximum "
            f"allowed size of {config.MAX_FILE_SIZE_BYTES} bytes."
        )


def validate_and_load(file_path: str | os.PathLike) -> np.ndarray:
    """
    Validate an uploaded fingerprint image and return it as a grayscale uint8 array.

    Validation steps (all must pass before the image is decoded):
      1. Extension allowlist check.
      2. File size check (non-zero, ≤ MAX_FILE_SIZE_BYTES).
      3. Magic-byte check (prevents renamed-file attacks).
      4. Safe decode via OpenCV (raises on corrupt / malformed image).
      5. Dimension bounds check (MIN_IMAGE_DIM ≤ H, W ≤ MAX_IMAGE_DIM).

    Args:
        file_path: Path to the image file on disk.

    Returns:
        Grayscale uint8 NumPy array of shape (H, W).

    Raises:
        InputValidationError: If any validation check fails.
        FileNotFoundError:    If the file does not exist.
    """
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Image file not found: {file_path.name}")

    # --- Step 1: Extension check ---
    ext = _check_extension(file_path)

    # --- Step 2 + 3: Read raw bytes, size check, magic bytes ---
    with open(file_path, "rb") as fh:
        data = fh.read()

    _check_file_size(data)
    _check_magic_bytes(data, ext)

    # --- Step 4: Safe decode ---
    try:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    except Exception as exc:
        raise InputValidationError("Image decoding failed. The file may be corrupt.") from exc

    if img is None:
        raise InputValidationError("OpenCV could not decode the image. The file may be corrupt.")

    # --- Step 5: Dimension bounds ---
    h, w = img.shape
    if h < config.MIN_IMAGE_DIM or w < config.MIN_IMAGE_DIM:
        raise InputValidationError(
            f"Image dimensions ({w}x{h}) are below the minimum "
            f"({config.MIN_IMAGE_DIM}x{config.MIN_IMAGE_DIM})."
        )
    if h > config.MAX_IMAGE_DIM or w > config.MAX_IMAGE_DIM:
        raise InputValidationError(
            f"Image dimensions ({w}x{h}) exceed the maximum "
            f"({config.MAX_IMAGE_DIM}x{config.MAX_IMAGE_DIM})."
        )

    # Log only a hash — NEVER log raw bytes or file path
    _logger.info("Image validated. hash=%s dims=%dx%d", _file_hash(data), w, h)
    return img


def validate_and_load_bytes(data: bytes, filename: str) -> np.ndarray:
    """
    Validate a file uploaded as bytes (e.g. from Streamlit's file_uploader).

    Args:
        data:     Raw file bytes.
        filename: Original filename (used for extension check only).

    Returns:
        Grayscale uint8 NumPy array.
    """
    ext = _check_extension(filename)
    _check_file_size(data)
    _check_magic_bytes(data, ext)

    try:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    except Exception as exc:
        raise InputValidationError("Image decoding failed.") from exc

    if img is None:
        raise InputValidationError("OpenCV could not decode the image.")

    h, w = img.shape
    if h < config.MIN_IMAGE_DIM or w < config.MIN_IMAGE_DIM:
        raise InputValidationError(f"Image too small: {w}x{h}.")
    if h > config.MAX_IMAGE_DIM or w > config.MAX_IMAGE_DIM:
        raise InputValidationError(f"Image too large: {w}x{h}.")

    _logger.info("Bytes-image validated. hash=%s dims=%dx%d", _file_hash(data), w, h)
    return img


# ─── 2. Normalisation (Paper §3.1) ────────────────────────────────────────────

def normalise(image: np.ndarray) -> np.ndarray:
    """
    Normalise a grayscale fingerprint image to zero mean and unit variance.

    Paper reference: §3.1
    Formula: I_norm = (I - mean(I)) / std(I)
    Result is clipped to [0, 255] and returned as float32 in range [0, 1].

    Args:
        image: Grayscale uint8 array (H, W).

    Returns:
        Normalised float32 array (H, W) in [0.0, 1.0].
    """
    img = image.astype(np.float32)
    mean = img.mean()
    std = img.std()
    if std < 1e-6:
        _logger.warning("Image has near-zero std; returning uniform image.")
        return np.zeros_like(img)
    normalised = (img - mean) / std
    # Clip to a reasonable range and scale to [0, 1]
    normalised = np.clip(normalised, -3.0, 3.0)
    normalised = (normalised + 3.0) / 6.0
    return normalised.astype(np.float32)
