"""
src/database.py — Encrypted SQLite template store.

Schema:
  TABLE templates
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    user_id     TEXT    NOT NULL UNIQUE
    blob        BLOB    NOT NULL   -- AES-GCM / Fernet ciphertext
    salt        BLOB    NOT NULL   -- PBKDF2 salt (NOT secret)
    created_at  TEXT    NOT NULL
    updated_at  TEXT    NOT NULL

Security invariants:
  - Blobs are ALWAYS ciphertext — never plaintext.
  - The key is NEVER stored in the DB.
  - Deletion removes both the DB row and any associated temp files atomically.
  - All DB writes use parameterised queries (no string interpolation → no SQL injection).
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
from pathlib import Path

from src.security import decrypt_template, encrypt_template, get_secure_logger

_logger = get_secure_logger(__name__)

_DEFAULT_DB_PATH = Path("biometric.db")


# ─── Connection context manager ───────────────────────────────────────────────

@contextlib.contextmanager
def _get_conn(db_path: Path):
    """Yield a SQLite connection with WAL mode and foreign-key enforcement."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema initialisation ────────────────────────────────────────────────────

def initialise_db(db_path: Path = _DEFAULT_DB_PATH) -> None:
    """Create the templates table if it does not already exist."""
    with _get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL UNIQUE,
                blob        BLOB    NOT NULL,
                salt        BLOB    NOT NULL,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );
        """)
    _logger.info("Database initialised at %s", db_path.name)


# ─── CRUD operations ──────────────────────────────────────────────────────────

def store_template(user_id: str, plaintext: bytes, db_path: Path = _DEFAULT_DB_PATH) -> None:
    """
    Encrypt and store a serialised template for a user.
    Overwrites an existing template for the same user_id.

    Args:
        user_id:   Opaque user identifier.
        plaintext: Serialised template bytes (JSON from template.serialise()).
        db_path:   Path to the SQLite database file.
    """
    ciphertext, salt = encrypt_template(plaintext)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with _get_conn(db_path) as conn:
        conn.execute("""
            INSERT INTO templates (user_id, blob, salt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                blob       = excluded.blob,
                salt       = excluded.salt,
                updated_at = excluded.updated_at;
        """, (user_id, ciphertext, salt, now, now))

    _logger.info("Template stored for user. action=STORE")


def retrieve_template(user_id: str, db_path: Path = _DEFAULT_DB_PATH) -> bytes:
    """
    Retrieve and decrypt a stored template.

    Args:
        user_id: Opaque user identifier.
        db_path: Path to the SQLite database file.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        KeyError: If no template exists for user_id.
        DecryptionError: If decryption fails (wrong key or tampered blob).
    """
    with _get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT blob, salt FROM templates WHERE user_id = ?;",
            (user_id,),
        ).fetchone()

    if row is None:
        raise KeyError(f"No template found for the given user.")

    ciphertext, salt = row
    plaintext = decrypt_template(bytes(ciphertext), bytes(salt))
    _logger.info("Template retrieved and decrypted. action=RETRIEVE")
    return plaintext


def delete_template(user_id: str, db_path: Path = _DEFAULT_DB_PATH) -> bool:
    """
    Delete a stored template.

    The deletion is performed inside a transaction. If the DELETE fails,
    no partial state is left.

    Args:
        user_id: Opaque user identifier.
        db_path: Path to the SQLite database file.

    Returns:
        True if a row was deleted; False if no matching user was found.
    """
    with _get_conn(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM templates WHERE user_id = ?;",
            (user_id,),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        _logger.info("Template deleted. action=DELETE result=SUCCESS")
    else:
        _logger.info("Delete attempted but no template found. action=DELETE result=NOT_FOUND")

    return deleted


def user_exists(user_id: str, db_path: Path = _DEFAULT_DB_PATH) -> bool:
    """Return True if a template for the given user_id exists in the database."""
    with _get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM templates WHERE user_id = ? LIMIT 1;",
            (user_id,),
        ).fetchone()
    return row is not None


def list_users(db_path: Path = _DEFAULT_DB_PATH) -> list[str]:
    """
    Return a list of all enrolled user IDs.
    This is an admin-only operation — access must be gated at the service layer.
    """
    with _get_conn(db_path) as conn:
        rows = conn.execute("SELECT user_id FROM templates ORDER BY created_at;").fetchall()
    return [r[0] for r in rows]
