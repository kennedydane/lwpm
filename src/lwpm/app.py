"""The lwpm Textual application.

This is the only place the derived master key lives, and it lives only in
memory (specification.md §4). The app owns the two security timers:

* a 5-minute idle timer that locks the vault (zeroes the key), reset on any
  keystroke;
* a 30-second timer that clears the clipboard after a copy.
"""

from __future__ import annotations

import os
from pathlib import Path

import pyperclip
from textual.app import App

from lwpm import crypto
from lwpm.storage import DEFAULT_DB_PATH, Vault
from lwpm.screens.auth import AuthScreen
from lwpm.screens.vault import VaultScreen

#: Idle seconds before the vault auto-locks (specification.md §4).
KEY_TIMEOUT = 300.0
#: Seconds before a copied value is cleared from the clipboard.
CLIP_TIMEOUT = 30.0


class LwpmApp(App):
    """Lightweight Password Manager."""

    TITLE = "lwpm"
    CSS_PATH = "lwpm.tcss"

    #: Argon2id parameters; overridable so tests can derive keys cheaply.
    kdf_params: dict = {}

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH, **kwargs):
        super().__init__(**kwargs)
        self._db_path = db_path
        self.vault: Vault | None = None
        #: The in-memory Fernet key. None means locked.
        self.key: bytes | None = None
        self.salt: bytes | None = None
        self._key_timer = None
        self._clip_timer = None

    # -- lifecycle ------------------------------------------------------

    def on_mount(self) -> None:
        self.vault = Vault(self._db_path)
        self.push_screen(AuthScreen())

    def on_unmount(self) -> None:
        if self.vault is not None:
            self.vault.close()

    # -- key derivation helpers ----------------------------------------

    def derive_key(self, password: str, salt: bytes) -> bytes:
        return crypto.derive_key(password, salt, **self.kdf_params)

    # -- lock / unlock --------------------------------------------------

    def unlock(self, key: bytes, salt: bytes) -> None:
        """Hold the key in memory, start the idle timer, show the vault."""
        self.key = key
        self.salt = salt
        self.reset_key_timer()
        self.switch_screen(VaultScreen())

    def lock(self) -> None:
        """Zero the key and return to the authentication screen."""
        self.key = None
        self.salt = None
        if self._key_timer is not None:
            self._key_timer.stop()
            self._key_timer = None
        # Replace the whole stack with a fresh auth screen.
        self.switch_screen(AuthScreen())

    def reset_key_timer(self) -> None:
        """(Re)start the idle auto-lock timer."""
        if self._key_timer is not None:
            self._key_timer.stop()
        self._key_timer = self.set_timer(KEY_TIMEOUT, self.lock)

    def on_key(self) -> None:
        # Any keystroke counts as activity and defers the auto-lock.
        if self.key is not None:
            self.reset_key_timer()

    # -- clipboard ------------------------------------------------------

    def copy_to_clipboard_value(self, value: str, label: str) -> None:
        """Copy a value and arm the 30-second clipboard-clear timer."""
        pyperclip.copy(value)
        if self._clip_timer is not None:
            self._clip_timer.stop()
        self._clip_timer = self.set_timer(CLIP_TIMEOUT, self.clear_clipboard)
        self.notify(f"{label} copied. Clipboard clears in {int(CLIP_TIMEOUT)}s.")

    def clear_clipboard(self) -> None:
        pyperclip.copy("")
        self._clip_timer = None


def main() -> None:
    """Console entry point: run the app against the configured vault DB."""
    db_path = os.environ.get("LWPM_DB", str(Path.home() / ".lwpm.db"))
    LwpmApp(db_path=db_path).run()
