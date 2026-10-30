"""
tests/test_preprocessing.py — Unit and security tests for the preprocessing module.

Tests cover:
  - Normal happy-path: valid BMP/PNG/TIFF images load correctly
  - Extension allowlist: wrong extensions are rejected
  - Magic-byte check: renamed files are rejected
  - File size limits: oversized and zero-byte files are rejected
  - Dimension bounds: too-small and too-large images are rejected
  - Corruption: truncated/random-bytes files are rejected
  - Normalisation: output range and dtype
"""

from __future__ import annotations

import struct

import numpy as np
import pytest

import config
from src.preprocessing import (
    InputValidationError,
    normalise,
    validate_and_load_bytes,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_bmp(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal grayscale BMP in memory."""
    import cv2
    img = np.zeros((height, width), dtype=np.uint8) + 128
    success, buf = cv2.imencode(".bmp", img)
    assert success
    return buf.tobytes()


def _make_png(width: int = 100, height: int = 100) -> bytes:
    import cv2
    img = np.zeros((height, width), dtype=np.uint8) + 64
    success, buf = cv2.imencode(".png", img)
    assert success
    return buf.tobytes()


# ─── Happy path ───────────────────────────────────────────────────────────────

def test_valid_bmp_loads():
    data = _make_bmp()
    img = validate_and_load_bytes(data, "finger.bmp")
    assert img.ndim == 2
    assert img.dtype == np.uint8


def test_valid_png_loads():
    data = _make_png()
    img = validate_and_load_bytes(data, "finger.png")
    assert img.ndim == 2


# ─── Extension allowlist ──────────────────────────────────────────────────────

def test_rejects_jpg_extension():
    data = _make_png()
    with pytest.raises(InputValidationError, match="extension"):
        validate_and_load_bytes(data, "finger.jpg")


def test_rejects_pdf_extension():
    with pytest.raises(InputValidationError, match="extension"):
        validate_and_load_bytes(b"%PDF-1.4", "finger.pdf")


def test_rejects_no_extension():
    with pytest.raises(InputValidationError, match="extension"):
        validate_and_load_bytes(_make_bmp(), "fingerprint")


# ─── Magic-byte check ─────────────────────────────────────────────────────────

def test_rejects_pdf_renamed_as_bmp():
    """A PDF file renamed to .bmp must be rejected by magic-byte check."""
    pdf_bytes = b"%PDF-1.4 fake content" + b"\x00" * 100
    with pytest.raises(InputValidationError, match="magic"):
        validate_and_load_bytes(pdf_bytes, "finger.bmp")


def test_rejects_xml_renamed_as_png():
    """An XML file renamed to .png must be rejected."""
    xml_bytes = b"<?xml version=\"1.0\"?><root/>" + b"\x00" * 100
    with pytest.raises(InputValidationError, match="magic"):
        validate_and_load_bytes(xml_bytes, "finger.png")


# ─── File size limits ─────────────────────────────────────────────────────────

def test_rejects_zero_byte_file():
    with pytest.raises(InputValidationError, match="empty"):
        validate_and_load_bytes(b"", "finger.bmp")


def test_rejects_oversized_file():
    big = _make_bmp() + b"\x00" * (config.MAX_FILE_SIZE_BYTES + 1)
    with pytest.raises(InputValidationError, match="size"):
        validate_and_load_bytes(big, "finger.bmp")


# ─── Dimension bounds ─────────────────────────────────────────────────────────

def test_rejects_too_small_image():
    import cv2
    tiny = np.zeros((10, 10), dtype=np.uint8)
    _, buf = cv2.imencode(".bmp", tiny)
    with pytest.raises(InputValidationError, match="too small|minimum"):
        validate_and_load_bytes(buf.tobytes(), "tiny.bmp")


def test_rejects_too_large_image():
    # Build a BMP header claiming a huge image without allocating the full array
    # We'll create a valid-looking large BMP header and check the size path
    import cv2
    # Just create a real image that's within limits but confirm we can probe the path
    big_img = np.zeros((config.MAX_IMAGE_DIM + 1, 100), dtype=np.uint8)
    _, buf = cv2.imencode(".bmp", big_img)
    with pytest.raises(InputValidationError, match="too large|maximum"):
        validate_and_load_bytes(buf.tobytes(), "big.bmp")


# ─── Corrupt files ────────────────────────────────────────────────────────────

def test_rejects_random_bytes_as_bmp():
    """Random bytes with BMP magic header but corrupt body are rejected at decode."""
    random_bmp = b"BM" + b"\xff" * 200
    with pytest.raises(InputValidationError):
        validate_and_load_bytes(random_bmp, "corrupt.bmp")


def test_rejects_truncated_png():
    data = _make_png()[:50]  # truncate to break the PNG structure
    # Truncated PNG may fail magic (too short) or decode
    with pytest.raises(InputValidationError):
        validate_and_load_bytes(data, "truncated.png")


# ─── Normalisation ────────────────────────────────────────────────────────────

def test_normalise_output_range():
    img = (np.random.rand(100, 100) * 255).astype(np.uint8)
    result = normalise(img)
    assert result.dtype == np.float32
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_normalise_uniform_image():
    """A completely uniform image should return zeros (near-zero std)."""
    img = np.full((100, 100), 128, dtype=np.uint8)
    result = normalise(img)
    assert result.max() == 0.0
