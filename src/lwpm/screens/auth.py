"""Authentication screen: first-run vault initialization and unlock."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label

from lwpm import crypto


class AuthScreen(Screen):
    """Prompts for the master password (or sets one on first run)."""

    def compose(self) -> ComposeResult:
        with Vertical(id='auth-box'):
            yield Label('Enter Master Password', id='auth-title')
            yield Input(password=True, id='password', placeholder='master password')
            yield Input(password=True, id='confirm', placeholder='confirm master password')
            yield Label('', id='auth-error')

    def on_mount(self) -> None:
        self._first_run = not self.app.vault.is_initialized()
        title = self.query_one('#auth-title', Label)
        confirm = self.query_one('#confirm', Input)
        if self._first_run:
            title.update('Set a Master Password')
            confirm.display = True
        else:
            confirm.display = False
        self.query_one('#password', Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _error(self, message: str) -> None:
        self.query_one('#auth-error', Label).update(message)

    def _submit(self) -> None:
        password = self.query_one('#password', Input).value
        if not password:
            self._error('Password must not be empty.')
            return

        if self._first_run:
            self._initialize(password)
        else:
            self._unlock(password)

    def _initialize(self, password: str) -> None:
        confirm = self.query_one('#confirm', Input).value
        if password != confirm:
            self._error('Passwords do not match.')
            return
        salt = crypto.generate_salt()
        key = self.app.derive_key(password, salt)
        self.app.vault.initialize(salt=salt, verification_blob=crypto.make_verification_blob(key))
        self.app.unlock(key, salt)

    def _unlock(self, password: str) -> None:
        salt, verification_blob = self.app.vault.get_config()
        key = self.app.derive_key(password, salt)
        if crypto.verify_key(key, verification_blob):
            self.app.unlock(key, salt)
        else:
            self._error('Incorrect password.')
            self.query_one('#password', Input).value = ''
