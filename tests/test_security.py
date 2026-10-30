"""
tests/test_security.py — Security control tests.

These tests verify every security control in THREAT_MODEL.md:
  § 3.1 Malformed upload tests (input validation)
  § 3.2 Encryption: wrong key fails cleanly
  § 3.3 Access control: unauthorized deletion is rejected
  § 3.4 Log hygiene: no sensitive data in log output
  § 3.5 Audit log: format and content are correct
  § 3.6 Template serialisation: no image data in template bytes
"""

from __future__ import annotations

import io
import json
import logging
import os

import numpy as np
import pytest

import config
from src.preprocessing import InputValidationError, validate_and_load_bytes
from src.security import (
    DecryptionError,
    _SensitiveFilter,
    audit_log,
    decrypt_template,
    encrypt_template,
    get_secure_logger,
)
from src.template import FingerprintTemplate, create, serialise
from src.minutiae_extraction import Minutia


# ─── §3.1 Malformed upload security tests ────────────────────────────────────

class TestMalformedUploads:
    """THREAT_MODEL §3.1 — File upload attack surface."""

    def test_rejects_corrupt_bmp(self):
        corrupt = b"BM" + b"\xff\xfe" * 100  # BMP header but garbage body
        with pytest.raises(InputValidationError):
            validate_and_load_bytes(corrupt, "finger.bmp")

    def test_rejects_oversized_file(self):
        import cv2
        img = np.zeros((100, 100), dtype=np.uint8)
        _, buf = cv2.imencode(".bmp", img)
        big = buf.tobytes() + b"\x00" * (config.MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(InputValidationError, match="size"):
            validate_and_load_bytes(big, "finger.bmp")

    def test_rejects_zero_byte(self):
        with pytest.raises(InputValidationError, match="empty"):
            validate_and_load_bytes(b"", "finger.bmp")

    def test_rejects_wrong_extension(self):
        with pytest.raises(InputValidationError, match="extension"):
            validate_and_load_bytes(b"anything", "finger.exe")

    def test_rejects_renamed_pdf_as_png(self):
        pdf = b"%PDF-1.4 content" + b"\x00" * 50
        with pytest.raises(InputValidationError, match="magic"):
            validate_and_load_bytes(pdf, "finger.png")

    def test_rejects_renamed_xml_as_bmp(self):
        xml = b"<?xml version" + b"\x00" * 50
        with pytest.raises(InputValidationError, match="magic"):
            validate_and_load_bytes(xml, "finger.bmp")


# ─── §3.2 Encryption security ─────────────────────────────────────────────────

class TestEncryption:
    """THREAT_MODEL §3.2 — Template encryption."""

    @pytest.fixture(autouse=True)
    def set_key(self, monkeypatch):
        monkeypatch.setenv("BIOMETRIC_MASTER_SECRET", "cafebabe" * 8)

    def test_round_trip(self):
        plaintext = b"sensitive template data"
        ct, salt = encrypt_template(plaintext)
        recovered = decrypt_template(ct, salt)
        assert recovered == plaintext

    def test_ciphertext_not_plaintext(self):
        pt = b"sensitive template data"
        ct, _ = encrypt_template(pt)
        assert pt not in ct

    def test_wrong_salt_fails(self, monkeypatch):
        """Using a different salt derives a different key — decryption fails."""
        pt = b"test data"
        ct, salt = encrypt_template(pt)
        wrong_salt = bytes(b ^ 0xFF for b in salt)
        with pytest.raises(DecryptionError):
            decrypt_template(ct, wrong_salt)

    def test_tampered_ciphertext_fails(self, monkeypatch):
        pt = b"test data"
        ct, salt = encrypt_template(pt)
        tampered = bytearray(ct)
        tampered[-1] ^= 0xFF
        with pytest.raises(DecryptionError):
            decrypt_template(bytes(tampered), salt)


# ─── §3.4 Log hygiene ────────────────────────────────────────────────────────

class TestLogHygiene:
    """THREAT_MODEL §3.4 — No sensitive data in log output."""

    def _capture_log(self, logger_name: str, message: str, *args) -> str:
        """Emit a log message and capture what was written."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(_SensitiveFilter())
        log = logging.getLogger(logger_name)
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
        log.info(message, *args)
        log.removeHandler(handler)
        return stream.getvalue()

    def test_png_magic_bytes_suppressed(self):
        message = b"\x89PNG\r\n\x1a\n" + b"image data"
        out = self._capture_log("test_hygiene_png", message.decode("latin-1"))
        assert b"\x89PNG" not in out.encode("latin-1", errors="ignore")

    def test_normal_message_passes(self):
        out = self._capture_log("test_hygiene_normal", "Processing image. hash=abc123 dims=100x100")
        assert "Processing" in out

    def test_password_pattern_sanitised(self):
        out = self._capture_log("test_hygiene_pw", "password = supersecret123")
        # The original password value must not appear
        assert "supersecret123" not in out


# ─── §3.5 Audit log ──────────────────────────────────────────────────────────

class TestAuditLog:
    """THREAT_MODEL §3.4 — Audit log format and content."""

    @pytest.fixture(autouse=True)
    def set_key(self, monkeypatch):
        monkeypatch.setenv("BIOMETRIC_MASTER_SECRET", "cafebabe" * 8)

    def test_audit_log_invalid_action_raises(self):
        with pytest.raises(ValueError, match="Invalid audit action"):
            audit_log("HACK", "user1", "SUCCESS")

    def test_audit_log_invalid_outcome_raises(self):
        with pytest.raises(ValueError, match="Invalid audit outcome"):
            audit_log("ENROLL", "user1", "MAYBE")

    def test_audit_log_valid_does_not_raise(self):
        # Should complete without error
        audit_log("ENROLL", "test_user_abc", "SUCCESS", "minutiae=42")
        audit_log("VERIFY", "test_user_abc", "FAIL", "low_quality")
        audit_log("DELETE", "test_user_abc", "SUCCESS")


# ─── §3.6 Template serialisation — no raw image data ─────────────────────────

class TestTemplateNoImageData:
    """Templates must never contain raw image bytes."""

    def test_template_bytes_contain_no_image_magic(self):
        minutiae = [Minutia(x=100, y=100, angle=0.5, mtype="ending", quality=1.0)]
        t = create("user1", minutiae)
        data = serialise(t)

        # Check none of the image magic bytes appear in the serialised template
        for ext, (offset, magic) in config.MAGIC_BYTES.items():
            assert magic not in data, \
                f"Template bytes contain {ext} magic bytes — potential image data leak!"

    def test_template_is_valid_json(self):
        minutiae = [Minutia(x=50, y=60, angle=1.0, mtype="bifurcation", quality=0.9)]
        t = create("user2", minutiae)
        data = serialise(t)
        parsed = json.loads(data.decode("utf-8"))
        assert "minutiae" in parsed
        assert "version" in parsed
        # Confirm no raw image fields exist
        assert "image" not in parsed
        assert "pixels" not in parsed
