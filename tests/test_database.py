"""
tests/test_database.py — Tests for the encrypted template store.

Tests:
  - Store and retrieve: round-trip decrypts to the original plaintext
  - Ciphertext is opaque: stored BLOB is not equal to plaintext
  - Wrong key fails: tampered BLOB raises DecryptionError
  - Deletion: row removed, user_exists returns False
  - Residual data: no data remains after delete
  - Duplicate user: second store overwrites without error
  - List users: admin operation works
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.database import (
    delete_template,
    initialise_db,
    list_users,
    retrieve_template,
    store_template,
    user_exists,
)
from src.security import DecryptionError


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_env_key(monkeypatch):
    """Set a test master secret so key derivation works without a .env file."""
    monkeypatch.setenv("BIOMETRIC_MASTER_SECRET", "deadbeef" * 8)  # 64 hex chars = 32 bytes


@pytest.fixture
def tmp_db(tmp_path) -> Path:
    db = tmp_path / "test.db"
    initialise_db(db)
    return db


PLAINTEXT = b'{"version":"1.0","user_id":"alice","minutiae":[]}'


# ─── Round-trip ───────────────────────────────────────────────────────────────

def test_store_and_retrieve_roundtrip(tmp_db):
    store_template("alice", PLAINTEXT, tmp_db)
    retrieved = retrieve_template("alice", tmp_db)
    assert retrieved == PLAINTEXT


# ─── Ciphertext opacity ───────────────────────────────────────────────────────

def test_stored_blob_is_not_plaintext(tmp_db):
    """The raw bytes stored in the DB must not equal the plaintext."""
    import sqlite3
    store_template("alice", PLAINTEXT, tmp_db)
    conn = sqlite3.connect(str(tmp_db))
    row = conn.execute("SELECT blob FROM templates WHERE user_id='alice'").fetchone()
    conn.close()
    stored_blob = bytes(row[0])
    assert stored_blob != PLAINTEXT
    # Ensure plaintext content is not visible inside the BLOB
    assert b"minutiae" not in stored_blob


# ─── Deletion ─────────────────────────────────────────────────────────────────

def test_delete_removes_user(tmp_db):
    store_template("bob", PLAINTEXT, tmp_db)
    assert user_exists("bob", tmp_db)
    deleted = delete_template("bob", tmp_db)
    assert deleted is True
    assert not user_exists("bob", tmp_db)


def test_delete_nonexistent_user_returns_false(tmp_db):
    result = delete_template("nobody", tmp_db)
    assert result is False


def test_no_residual_data_after_delete(tmp_db):
    """After deletion, retrieve should raise KeyError."""
    store_template("carol", PLAINTEXT, tmp_db)
    delete_template("carol", tmp_db)
    with pytest.raises(KeyError):
        retrieve_template("carol", tmp_db)


# ─── User existence ───────────────────────────────────────────────────────────

def test_user_exists_returns_false_for_unknown(tmp_db):
    assert not user_exists("unknown_user", tmp_db)


def test_user_exists_returns_true_after_store(tmp_db):
    store_template("dave", PLAINTEXT, tmp_db)
    assert user_exists("dave", tmp_db)


# ─── Overwrite ────────────────────────────────────────────────────────────────

def test_second_store_overwrites(tmp_db):
    store_template("eve", PLAINTEXT, tmp_db)
    new_plaintext = b'{"version":"1.0","user_id":"eve","minutiae":[{"x":1}]}'
    store_template("eve", new_plaintext, tmp_db)
    retrieved = retrieve_template("eve", tmp_db)
    assert retrieved == new_plaintext


# ─── List users ───────────────────────────────────────────────────────────────

def test_list_users(tmp_db):
    store_template("user1", PLAINTEXT, tmp_db)
    store_template("user2", PLAINTEXT, tmp_db)
    users = list_users(tmp_db)
    assert "user1" in users
    assert "user2" in users


# ─── Decryption with tampered blob ────────────────────────────────────────────

def test_tampered_blob_raises_decryption_error(tmp_db):
    """Flipping bytes in the stored blob should cause DecryptionError."""
    import sqlite3
    store_template("frank", PLAINTEXT, tmp_db)

    # Tamper with the blob directly in SQLite
    conn = sqlite3.connect(str(tmp_db))
    row = conn.execute("SELECT blob FROM templates WHERE user_id='frank'").fetchone()
    blob = bytearray(row[0])
    blob[-1] ^= 0xFF  # flip last byte
    conn.execute("UPDATE templates SET blob=? WHERE user_id='frank'", (bytes(blob),))
    conn.commit()
    conn.close()

    with pytest.raises(DecryptionError):
        retrieve_template("frank", tmp_db)
