"""SQLite vault storage for lwpm.

Owns the schema and all SQL. Holds no master key and knows nothing about
cryptography: secret blobs are opaque bytes, and re-keying is driven by a
caller-supplied re-encrypt callable. See specification.md §2.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_DB_PATH = Path.home() / ".lwpm.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    id                INTEGER PRIMARY KEY,
    salt              BLOB NOT NULL,
    verification_blob BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS credentials (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    secret_blob BLOB NOT NULL,
    created_at  TEXT,
    updated_at  TEXT
);
"""


class AlreadyInitializedError(Exception):
    """Raised when initializing a vault that already has a config row."""


class DuplicateNameError(Exception):
    """Raised when a credential name collides with an existing one."""


@dataclass(frozen=True)
class Credential:
    id: int
    name: str
    secret_blob: bytes
    created_at: str
    updated_at: str


class Vault:
    """A connection to a single lwpm SQLite database file."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- vault config / initialization ----------------------------------

    def is_initialized(self) -> bool:
        row = self._conn.execute("SELECT 1 FROM config LIMIT 1").fetchone()
        return row is not None

    def initialize(self, *, salt: bytes, verification_blob: bytes) -> None:
        if self.is_initialized():
            raise AlreadyInitializedError("vault already initialized")
        self._conn.execute(
            "INSERT INTO config (id, salt, verification_blob) VALUES (1, ?, ?)",
            (salt, verification_blob),
        )
        self._conn.commit()

    def get_config(self) -> tuple[bytes, bytes]:
        row = self._conn.execute(
            "SELECT salt, verification_blob FROM config LIMIT 1"
        ).fetchone()
        if row is None:
            raise AlreadyInitializedError("vault is not initialized")
        return bytes(row[0]), bytes(row[1])

    # -- credential CRUD ------------------------------------------------

    def add_credential(
        self, name: str, secret_blob: bytes, *, created_at: str, updated_at: str
    ) -> None:
        try:
            self._conn.execute(
                "INSERT INTO credentials (name, secret_blob, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (name, secret_blob, created_at, updated_at),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateNameError(f"credential {name!r} already exists") from exc
        self._conn.commit()

    def update_credential(
        self,
        name: str,
        *,
        secret_blob: bytes,
        updated_at: str,
        new_name: str | None = None,
    ) -> None:
        target_name = new_name if new_name is not None else name
        try:
            self._conn.execute(
                "UPDATE credentials SET name = ?, secret_blob = ?, updated_at = ? "
                "WHERE name = ?",
                (target_name, secret_blob, updated_at, name),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateNameError(f"credential {target_name!r} already exists") from exc
        self._conn.commit()

    def delete_credential(self, name: str) -> None:
        self._conn.execute("DELETE FROM credentials WHERE name = ?", (name,))
        self._conn.commit()

    def get_credential(self, name: str) -> Credential | None:
        row = self._conn.execute(
            "SELECT id, name, secret_blob, created_at, updated_at "
            "FROM credentials WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return Credential(row[0], row[1], bytes(row[2]), row[3], row[4])

    def get_secret_blob(self, name: str) -> bytes:
        cred = self.get_credential(name)
        if cred is None:
            raise KeyError(name)
        return cred.secret_blob

    # -- listing / search -----------------------------------------------

    def list_names(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM credentials ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    def search_names(self, substring: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM credentials WHERE name LIKE ? ESCAPE '\\' "
            "ORDER BY name",
            (f"%{_escape_like(substring)}%",),
        ).fetchall()
        return [r[0] for r in rows]

    # -- re-keying ------------------------------------------------------

    def rekey(
        self,
        *,
        new_salt: bytes,
        new_verification_blob: bytes,
        reencrypt: Callable[[bytes], bytes],
    ) -> None:
        """Re-encrypt every secret blob and swap the config in one transaction.

        ``reencrypt`` maps an old secret_blob to a new one. If it raises (or any
        SQL fails) the whole operation rolls back, leaving the vault usable under
        the old key (specification.md §3).
        """
        try:
            rows = self._conn.execute(
                "SELECT id, secret_blob FROM credentials"
            ).fetchall()
            for cred_id, blob in rows:
                new_blob = reencrypt(bytes(blob))
                self._conn.execute(
                    "UPDATE credentials SET secret_blob = ? WHERE id = ?",
                    (new_blob, cred_id),
                )
            self._conn.execute(
                "UPDATE config SET salt = ?, verification_blob = ? WHERE id = 1",
                (new_salt, new_verification_blob),
            )
        except Exception:
            self._conn.rollback()
            raise
        self._conn.commit()


def _escape_like(text: str) -> str:
    """Escape LIKE wildcards so a search term matches literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
