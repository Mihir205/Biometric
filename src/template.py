"""
src/template.py — Biometric template definition and secure serialisation.

A template encapsulates the extracted minutiae for a single fingerprint impression.

Security invariants:
  - Templates NEVER contain raw image data — only derived minutiae features.
  - Serialisation uses JSON (human-readable schema) — not pickle (arbitrary code execution risk).
  - Template schema is versioned; version mismatch raises an explicit error.
  - Templates are encrypted before storage (see src/security.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import List

import config
from src.minutiae_extraction import Minutia
from src.security import get_secure_logger

_logger = get_secure_logger(__name__)


# ─── Template data model ──────────────────────────────────────────────────────

@dataclass
class FingerprintTemplate:
    """
    Biometric template for a single fingerprint impression.

    Fields:
        version:   Schema version string. Must match config.TEMPLATE_VERSION.
        user_id:   Opaque user identifier (stored in DB alongside encrypted BLOB).
        created_at: ISO-8601 timestamp of template creation.
        minutiae:  List of extracted minutiae (coordinates + angle + type).
        quality:   Overall template quality score [0.0, 1.0] (future use).
    """
    version: str
    user_id: str
    created_at: str
    minutiae: List[dict]   # [{"x": int, "y": int, "angle": float, "type": str, "quality": float}]
    quality: float = 1.0

    @property
    def minutiae_count(self) -> int:
        return len(self.minutiae)


class TemplateSerialisationError(Exception):
    """Raised when a template cannot be serialised or deserialised."""


class TemplateVersionError(Exception):
    """Raised when a deserialised template has an incompatible schema version."""


# ─── Factory ──────────────────────────────────────────────────────────────────

def create(user_id: str, minutiae: list[Minutia]) -> FingerprintTemplate:
    """
    Create a FingerprintTemplate from a list of Minutia objects.

    Truncates to MAX_MINUTIAE_PER_TEMPLATE if necessary.

    Args:
        user_id:  Opaque user identifier.
        minutiae: Filtered minutiae list from minutiae_extraction.remove_spurious().

    Returns:
        A FingerprintTemplate ready for serialisation.
    """
    if len(minutiae) > config.MAX_MINUTIAE_PER_TEMPLATE:
        _logger.warning(
            "Truncating minutiae from %d to %d.",
            len(minutiae), config.MAX_MINUTIAE_PER_TEMPLATE,
        )
        minutiae = minutiae[: config.MAX_MINUTIAE_PER_TEMPLATE]

    minutiae_dicts = [
        {
            "x": int(m.x),
            "y": int(m.y),
            "angle": float(m.angle),
            "type": m.mtype,
            "quality": float(m.quality),
        }
        for m in minutiae
    ]

    template = FingerprintTemplate(
        version=config.TEMPLATE_VERSION,
        user_id=user_id,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        minutiae=minutiae_dicts,
    )
    _logger.info("Template created. user_id_len=%d minutiae=%d", len(user_id), len(minutiae_dicts))
    return template


# ─── Serialisation (JSON — NOT pickle) ────────────────────────────────────────

def serialise(template: FingerprintTemplate) -> bytes:
    """
    Serialise a template to JSON bytes.

    Returns:
        UTF-8 encoded JSON bytes suitable for encryption and DB storage.
    """
    try:
        payload = {
            "version": template.version,
            "user_id": template.user_id,
            "created_at": template.created_at,
            "minutiae": template.minutiae,
            "quality": template.quality,
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TemplateSerialisationError("Template serialisation failed.") from exc


def deserialise(data: bytes) -> FingerprintTemplate:
    """
    Deserialise a template from JSON bytes (after decryption).

    Raises:
        TemplateVersionError: If the version does not match config.TEMPLATE_VERSION.
        TemplateSerialisationError: If the JSON is malformed.
    """
    try:
        payload = json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TemplateSerialisationError("Template deserialisation failed: invalid JSON.") from exc

    version = payload.get("version")
    if version != config.TEMPLATE_VERSION:
        raise TemplateVersionError(
            f"Template version mismatch: expected {config.TEMPLATE_VERSION!r}, got {version!r}."
        )

    return FingerprintTemplate(
        version=payload["version"],
        user_id=payload["user_id"],
        created_at=payload["created_at"],
        minutiae=payload["minutiae"],
        quality=payload.get("quality", 1.0),
    )
