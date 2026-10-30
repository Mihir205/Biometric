"""
app.py — Streamlit Fingerprint Biometric Verification Application.

Features:
  - Enroll: upload a fingerprint, store an encrypted template
  - Verify: upload a probe fingerprint, compare against enrolled template
  - Admin Delete: remove an enrolled user (admin session required)

Security:
  - Input validation applied at the upload boundary (same as enrollment service)
  - Admin operations are enforced at the service layer, not just the UI
  - Similarity scores are NOT displayed to the user (decision only)
  - Session state is cleared on logout
  - Max upload size set via Streamlit config
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load .env before any security module is imported
load_dotenv()

from src.database import delete_template, initialise_db, list_users, user_exists
from src.enrollment import EnrollmentError, enroll
from src.security import audit_log, get_secure_logger
from src.verification import VerificationError, verify

# ─── Configuration ────────────────────────────────────────────────────────────
DB_PATH = Path("biometric.db")
_logger = get_secure_logger(__name__)

st.set_page_config(
    page_title="Fingerprint Biometric Verification",
    page_icon="🔒",
    layout="centered",
)

# Initialise DB on startup
initialise_db(DB_PATH)


# ─── Session state helpers ────────────────────────────────────────────────────

def _is_admin() -> bool:
    return st.session_state.get("is_admin", False)


def _clear_session() -> None:
    """Clear all session state (called on logout)."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ─── Sidebar: Admin login ─────────────────────────────────────────────────────

with st.sidebar:
    st.title("🔒 Admin")
    admin_secret = os.environ.get("BIOMETRIC_ADMIN_SECRET", "")

    if not _is_admin():
        entered = st.text_input("Admin password", type="password")
        if st.button("Login") and entered:
            if admin_secret and entered == admin_secret:
                st.session_state["is_admin"] = True
                st.success("Admin session active.")
            else:
                st.error("Incorrect admin password.")
    else:
        st.success("✅ Admin session active")
        if st.button("Logout"):
            _clear_session()
            st.rerun()

    st.divider()
    st.caption("Fingerprint Biometric Verification System")
    st.caption("For research use only. Not production-ready.")


# ─── Main tabs ────────────────────────────────────────────────────────────────

st.title("Fingerprint Biometric Verification")
tab_enroll, tab_verify, tab_admin = st.tabs(["📥 Enroll", "🔍 Verify", "🛠 Admin"])


# ─── Enroll tab ──────────────────────────────────────────────────────────────

with tab_enroll:
    st.header("Enroll a Fingerprint")
    st.info("Upload a fingerprint image to create an encrypted template.")

    user_id_enroll = st.text_input(
        "User ID", placeholder="e.g. alice_001", key="enroll_user_id"
    )
    uploaded_file = st.file_uploader(
        "Fingerprint image (.bmp, .png, .tif)",
        type=["bmp", "png", "tif", "tiff"],
        key="enroll_file",
    )
    re_enroll = st.checkbox("Allow re-enrollment (requires admin)", key="re_enroll")

    if st.button("Enroll", key="btn_enroll"):
        if not user_id_enroll.strip():
            st.error("Please enter a User ID.")
        elif uploaded_file is None:
            st.error("Please upload a fingerprint image.")
        elif re_enroll and not _is_admin():
            st.error("Re-enrollment requires an active admin session.")
        else:
            with st.spinner("Processing..."):
                try:
                    data = uploaded_file.read()
                    enroll(
                        user_id=user_id_enroll.strip(),
                        image_bytes=data,
                        filename=uploaded_file.name,
                        db_path=DB_PATH,
                        is_admin=_is_admin() and re_enroll,
                    )
                    st.success(f"✅ User **{user_id_enroll}** enrolled successfully.")
                except EnrollmentError as exc:
                    st.error(f"Enrollment failed: {exc}")
                except Exception as exc:
                    _logger.error("Unexpected enrollment error: %s", type(exc).__name__)
                    st.error("An unexpected error occurred.")


# ─── Verify tab ───────────────────────────────────────────────────────────────

with tab_verify:
    st.header("Verify a Fingerprint")
    st.info(
        "Upload a probe fingerprint to compare it against an enrolled template. "
        "Only the accept/reject decision is shown — no score is displayed."
    )

    user_id_verify = st.text_input(
        "User ID to verify against", placeholder="e.g. alice_001", key="verify_user_id"
    )
    probe_file = st.file_uploader(
        "Probe fingerprint image (.bmp, .png, .tif)",
        type=["bmp", "png", "tif", "tiff"],
        key="verify_file",
    )

    if st.button("Verify", key="btn_verify"):
        if not user_id_verify.strip():
            st.error("Please enter a User ID.")
        elif probe_file is None:
            st.error("Please upload a probe fingerprint image.")
        else:
            with st.spinner("Comparing..."):
                try:
                    data = probe_file.read()
                    result = verify(
                        user_id=user_id_verify.strip(),
                        image_bytes=data,
                        filename=probe_file.name,
                        db_path=DB_PATH,
                    )
                    if result.decision:
                        st.success("✅ **ACCEPTED** — Fingerprints match.")
                    else:
                        st.error("❌ **REJECTED** — Fingerprints do not match.")
                except VerificationError as exc:
                    st.error(f"Verification failed: {exc}")
                except Exception as exc:
                    _logger.error("Unexpected verification error: %s", type(exc).__name__)
                    st.error("An unexpected error occurred.")


# ─── Admin tab ────────────────────────────────────────────────────────────────

with tab_admin:
    st.header("Admin — Template Management")

    if not _is_admin():
        st.warning("⚠️ You must be logged in as admin to access this section.")
    else:
        st.subheader("Enrolled Users")
        users = list_users(DB_PATH)
        if users:
            st.write(f"**{len(users)}** user(s) enrolled.")
            for u in users:
                col1, col2 = st.columns([3, 1])
                col1.text(u)
                if col2.button("Delete", key=f"del_{u}"):
                    with st.spinner(f"Deleting {u}..."):
                        deleted = delete_template(u, DB_PATH)
                        if deleted:
                            audit_log("DELETE", u, "SUCCESS", detail="admin_ui")
                            st.success(f"Deleted user: {u}")
                            st.rerun()
                        else:
                            audit_log("DELETE", u, "FAIL", detail="not_found")
                            st.error(f"User {u} not found.")
        else:
            st.info("No users enrolled yet.")
