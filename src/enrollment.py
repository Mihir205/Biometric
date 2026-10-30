"""
src/enrollment.py — Enrollment service.

Orchestrates the full enrollment pipeline:
  validate → normalise → orientation → enhance → segment → skeletonise
    → extract → remove_spurious → create_template → serialise → encrypt → store

Security:
  - Input validation is the very first step.
  - Access control: only authorised callers may enroll.
  - Audit log written on every attempt (success or failure).
  - Raw image is never persisted beyond this function call.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import config
from src import (
    database,
    enhancement,
    minutiae_extraction,
    orientation,
    preprocessing,
    segmentation,
    template as tmpl,
)
from src.security import audit_log, get_secure_logger

_logger = get_secure_logger(__name__)


class EnrollmentError(Exception):
    """Raised when enrollment fails for any reason."""


def enroll(
    user_id: str,
    image_bytes: bytes,
    filename: str,
    db_path: Path = Path("biometric.db"),
    is_admin: bool = False,
) -> None:
    """
    Enroll a user by processing a fingerprint image and storing an encrypted template.

    Args:
        user_id:     Opaque user identifier.
        image_bytes: Raw file bytes from the upload.
        filename:    Original filename (used for extension + magic-byte check).
        db_path:     Path to the SQLite database.
        is_admin:    Must be True to allow re-enrollment of an existing user.

    Raises:
        EnrollmentError: On validation failure or extraction failure.
    """
    try:
        # 1. Input validation (security boundary)
        img = preprocessing.validate_and_load_bytes(image_bytes, filename)

        # 2. Check for existing enrollment
        if database.user_exists(user_id, db_path) and not is_admin:
            raise EnrollmentError("User is already enrolled. Admin permission required to re-enroll.")

        # 3. Image pipeline
        normalised    = preprocessing.normalise(img)
        orient_field  = orientation.estimate(normalised)
        enhanced      = enhancement.enhance(normalised, orient_field)
        mask          = segmentation.segment(enhanced)
        skeleton      = segmentation.skeletonise(enhanced, mask)

        # 4. Minutiae extraction
        raw_minutiae      = minutiae_extraction.extract(skeleton, orient_field, mask)
        filtered_minutiae = minutiae_extraction.remove_spurious(raw_minutiae, skeleton)

        if len(filtered_minutiae) < 10:
            raise EnrollmentError(
                f"Insufficient minutiae extracted ({len(filtered_minutiae)}). "
                "Image quality may be too low."
            )

        # 5. Template creation and serialisation
        fingerprint_template = tmpl.create(user_id, filtered_minutiae)
        plaintext = tmpl.serialise(fingerprint_template)

        # 6. Encrypt and store
        database.store_template(user_id, plaintext, db_path)

        audit_log("ENROLL", user_id, "SUCCESS", f"minutiae={len(filtered_minutiae)}")

    except preprocessing.InputValidationError as exc:
        audit_log("ENROLL", user_id, "FAIL", "input_validation_error")
        raise EnrollmentError(f"Input validation failed: {exc}") from exc
    except EnrollmentError:
        audit_log("ENROLL", user_id, "FAIL", "enrollment_error")
        raise
    except Exception as exc:
        audit_log("ENROLL", user_id, "ERROR", "unexpected_error")
        raise EnrollmentError(f"Enrollment failed due to an unexpected error.") from exc
