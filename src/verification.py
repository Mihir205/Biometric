"""
src/verification.py — Verification service.

Orchestrates the full verification pipeline:
  validate probe → pipeline → extract → retrieve stored template
    → decrypt → deserialise → match → decision → audit log

Security:
  - Probe image is validated before any comparison.
  - Similarity score is NEVER logged — only the decision.
  - Audit log written on every attempt.
  - DecryptionError is caught and surfaced as VerificationError (no leakage of reason).
"""

from __future__ import annotations

from pathlib import Path

import config
from src import (
    database,
    enhancement,
    matching,
    minutiae_extraction,
    orientation,
    preprocessing,
    segmentation,
    template as tmpl,
)
from src.security import DecryptionError, audit_log, get_secure_logger

_logger = get_secure_logger(__name__)


class VerificationError(Exception):
    """Raised when verification cannot be completed."""


def verify(
    user_id: str,
    image_bytes: bytes,
    filename: str,
    db_path: Path = Path("biometric.db"),
) -> matching.MatchResult:
    """
    Verify a probe fingerprint image against the enrolled template for user_id.

    Args:
        user_id:     Opaque user identifier to look up.
        image_bytes: Raw file bytes of the probe fingerprint.
        filename:    Original filename (extension + magic-byte check).
        db_path:     Path to the SQLite database.

    Returns:
        MatchResult — contains the decision (True = same finger).
        NOTE: The score field is available for evaluation use but must not be logged.

    Raises:
        VerificationError: If the user is not enrolled, decryption fails, or
                           the probe image is invalid.
    """
    try:
        # 1. Validate probe image (same security boundary as enrollment)
        probe_img = preprocessing.validate_and_load_bytes(image_bytes, filename)

        # 2. Check enrollment
        if not database.user_exists(user_id, db_path):
            audit_log("VERIFY", user_id, "FAIL", "user_not_enrolled")
            raise VerificationError("User is not enrolled.")

        # 3. Process probe image through pipeline
        normalised   = preprocessing.normalise(probe_img)
        orient_field = orientation.estimate(normalised)
        enhanced     = enhancement.enhance(normalised, orient_field)
        mask         = segmentation.segment(enhanced)
        skeleton     = segmentation.skeletonise(enhanced, mask)

        raw_minutiae = minutiae_extraction.extract(skeleton, orient_field, mask)
        filtered     = minutiae_extraction.remove_spurious(raw_minutiae, skeleton)

        if len(filtered) < 5:
            audit_log("VERIFY", user_id, "FAIL", "insufficient_probe_minutiae")
            raise VerificationError("Probe image quality too low for matching.")

        probe_template = tmpl.create(user_id, filtered)

        # 4. Retrieve and decrypt stored template
        try:
            plaintext = database.retrieve_template(user_id, db_path)
        except KeyError:
            audit_log("VERIFY", user_id, "FAIL", "template_not_found")
            raise VerificationError("Enrolled template not found.")
        except DecryptionError:
            audit_log("VERIFY", user_id, "ERROR", "decryption_error")
            raise VerificationError("Could not decrypt the enrolled template.")

        stored_template = tmpl.deserialise(plaintext)

        # 5. Match
        result = matching.match(stored_template, probe_template)

        outcome = "SUCCESS" if result.decision else "FAIL"
        audit_log("VERIFY", user_id, outcome, f"matched={result.matched_pairs}")

        return result

    except VerificationError:
        raise
    except preprocessing.InputValidationError as exc:
        audit_log("VERIFY", user_id, "FAIL", "input_validation_error")
        raise VerificationError(f"Probe image validation failed: {exc}") from exc
    except Exception as exc:
        audit_log("VERIFY", user_id, "ERROR", "unexpected_error")
        raise VerificationError("Verification failed due to an unexpected error.") from exc
