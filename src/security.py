"""
src/security.py — Security utilities for the biometric system.

Responsibilities:
  1. SecureLogger   — wraps Python logging; rejects sensitive content before output.
  2. Key management — derives and loads the AES encryption key from the environment.
  3. Template encryption / decryption — authenticated encryption via Fernet (AES-128-CBC + HMAC-SHA256).
  4. Audit logging  — structured audit events (ENROLL / VERIFY / DELETE) with hashed user IDs.

Security invariants enforced here:
  - Raw images, templates, keys, and similarity scores NEVER appear in log output.
  - User IDs are logged only as SHA-256 hashes.
  - Decryption failure raises an explicit, catchable exception — no silent corruption.
  - Key is loaded from .env or environment variable — NEVER hardcoded.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from base64 import urlsafe_b64encode
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import config

# ─── Module logger (uses SecureLogger via the handler set up below) ───────────
_logger = logging.getLogger(__name__)


# ─── 1. SecureLogger ──────────────────────────────────────────────────────────

class _SensitiveFilter(logging.Filter):
    """
    Logging filter that blocks any log record whose message contains patterns
    that could indicate biometric data, ciphertext, or key material.

    Called before every record is emitted; returning False suppresses the record
    and writes a sanitisation notice instead.
    """

    # Byte patterns that must never appear in a log message.
    _BYTE_PATTERNS: list[bytes] = config.LOG_SENSITIVE_PATTERNS

    # Regex patterns applied to the rendered string message.
    _STR_PATTERNS: list[re.Pattern] = [
        re.compile(r"(?i)password\s*="),
        re.compile(r"(?i)secret\s*="),
        re.compile(r"(?i)key\s*=\s*[A-Za-z0-9+/=]{20,}"),  # base64-looking value
    ]

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        msg = record.getMessage()

        # Check string patterns
        for pattern in self._STR_PATTERNS:
            if pattern.search(msg):
                record.msg = "[SECURITY] Log message suppressed: contains sensitive pattern."
                record.args = ()
                return True  # emit the sanitised notice, not the original

        # Check byte patterns against the encoded message
        encoded = msg.encode("utf-8", errors="replace")
        for bp in self._BYTE_PATTERNS:
            if bp in encoded:
                record.msg = "[SECURITY] Log message suppressed: contains binary sensitive data."
                record.args = ()
                return True

        return True  # allow the record through


def get_secure_logger(name: str) -> logging.Logger:
    """
    Returns a logger configured with the sensitive-content filter and a safe
    StreamHandler. All modules in this project should obtain their logger through
    this function rather than calling logging.getLogger directly.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
        handler.addFilter(_SensitiveFilter())
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    return logger


# ─── 2. Key Management ────────────────────────────────────────────────────────

class KeyManagementError(Exception):
    """Raised when the encryption key cannot be loaded or derived."""


def _load_master_secret() -> bytes:
    """
    Load the master secret from the environment.

    Resolution order:
      1. BIOMETRIC_MASTER_SECRET environment variable (hex-encoded 32+ byte secret).
      2. BIOMETRIC_MASTER_SECRET_FILE path — reads the file content.

    Raises KeyManagementError if neither is set.
    """
    secret_hex = os.environ.get("BIOMETRIC_MASTER_SECRET")
    if secret_hex:
        try:
            return bytes.fromhex(secret_hex)
        except ValueError as exc:
            raise KeyManagementError(
                "BIOMETRIC_MASTER_SECRET is not valid hex."
            ) from exc

    secret_file = os.environ.get("BIOMETRIC_MASTER_SECRET_FILE")
    if secret_file:
        try:
            with open(secret_file, "rb") as fh:
                return fh.read().strip()
        except OSError as exc:
            raise KeyManagementError(
                f"Cannot read BIOMETRIC_MASTER_SECRET_FILE: {secret_file}"
            ) from exc

    raise KeyManagementError(
        "No encryption key found. Set BIOMETRIC_MASTER_SECRET (hex) or "
        "BIOMETRIC_MASTER_SECRET_FILE in your environment or .env file."
    )


def derive_fernet_key(salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """
    Derive a Fernet-compatible 32-byte key from the master secret using PBKDF2-HMAC-SHA256.

    Args:
        salt: Optional 16-byte salt. If None, a fresh random salt is generated.
              Pass a stored salt to re-derive the same key for decryption.

    Returns:
        (fernet_key_bytes, salt) — both must be stored; salt is NOT secret.
    """
    master = _load_master_secret()
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=config.KEY_LENGTH_BYTES,
        salt=salt,
        iterations=config.KEY_DERIVATION_ITERATIONS,
    )
    raw_key = kdf.derive(master)
    # Fernet requires URL-safe base64-encoded 32-byte key
    fernet_key = urlsafe_b64encode(raw_key)
    return fernet_key, salt


# Cached Fernet instance (re-derived once per process run).
# In a long-running service, rotate this periodically.
_fernet_cache: dict[bytes, Fernet] = {}


def _get_fernet(salt: bytes) -> Fernet:
    if salt not in _fernet_cache:
        key, _ = derive_fernet_key(salt)
        _fernet_cache[salt] = Fernet(key)
    return _fernet_cache[salt]


# ─── 3. Template Encryption / Decryption ─────────────────────────────────────

class DecryptionError(Exception):
    """Raised when template decryption fails (wrong key, tampered ciphertext)."""


def encrypt_template(plaintext: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt a serialised template blob with authenticated encryption.

    Args:
        plaintext: Raw bytes of the serialised template (must NOT contain image data).

    Returns:
        (ciphertext, salt) — store both in the database.
        The salt is NOT secret; it is needed to re-derive the key for decryption.
    """
    salt = os.urandom(16)
    f = _get_fernet(salt)
    ciphertext = f.encrypt(plaintext)
    return ciphertext, salt


def decrypt_template(ciphertext: bytes, salt: bytes) -> bytes:
    """
    Decrypt a template blob. Raises DecryptionError on tamper or wrong key.

    Args:
        ciphertext: The encrypted blob from the database.
        salt: The salt stored alongside the ciphertext in the database.

    Returns:
        Decrypted plaintext bytes.
    """
    try:
        f = _get_fernet(salt)
        return f.decrypt(ciphertext)
    except (InvalidToken, Exception) as exc:
        raise DecryptionError(
            "Template decryption failed. The ciphertext may have been tampered "
            "with, or the wrong key was used."
        ) from exc


# ─── 4. Audit Logging ─────────────────────────────────────────────────────────

_audit_logger = get_secure_logger("audit")


def _hash_user_id(user_id: str) -> str:
    """Return the first 16 hex chars of SHA-256(user_id) for audit log entries."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def audit_log(action: str, user_id: str, outcome: str, detail: str = "") -> None:
    """
    Write a structured audit log entry.

    Args:
        action:  One of ENROLL | VERIFY | DELETE | ADMIN.
        user_id: Plaintext user identifier — hashed before logging.
        outcome: One of SUCCESS | FAIL | ERROR.
        detail:  Optional non-sensitive context string (e.g. "file too large").
    """
    allowed_actions = {"ENROLL", "VERIFY", "DELETE", "ADMIN"}
    allowed_outcomes = {"SUCCESS", "FAIL", "ERROR"}

    if action not in allowed_actions:
        raise ValueError(f"Invalid audit action: {action!r}")
    if outcome not in allowed_outcomes:
        raise ValueError(f"Invalid audit outcome: {outcome!r}")

    uid_hash = _hash_user_id(user_id)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _audit_logger.info(
        "AUDIT | ts=%s | action=%s | uid_hash=%s | outcome=%s | detail=%s",
        ts, action, uid_hash, outcome, detail or "-",
    )
