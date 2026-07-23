"""Change Master Password modal — drives the atomic re-key flow (spec §3)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from lwpm import crypto


class ChangePasswordModal(ModalScreen[bool]):
    """Verifies the current password, then re-encrypts the whole vault."""

    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def compose(self) -> ComposeResult:
        with Vertical(id='change-box'):
            yield Label('Change Master Password', id='change-title')
            yield Input(password=True, placeholder='current password', id='current')
            yield Input(password=True, placeholder='new password', id='new')
            yield Input(password=True, placeholder='confirm new password', id='confirm')
            yield Label('', id='change-error')
            with Horizontal(id='change-buttons'):
                yield Button('Change', variant='primary', id='change')
                yield Button('Cancel', id='cancel')

    def on_mount(self) -> None:
        self.query_one('#current', Input).focus()

    def _error(self, message: str) -> None:
        self.query_one('#change-error', Label).update(message)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'change':
            self._submit()
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _submit(self) -> None:
        current = self.query_one('#current', Input).value
        new = self.query_one('#new', Input).value
        confirm = self.query_one('#confirm', Input).value

        salt, verification_blob = self.app.vault.get_config()
        old_key = self.app.derive_key(current, salt)
        if not crypto.verify_key(old_key, verification_blob):
            self._error('Current password is incorrect.')
            return
        if not new:
            self._error('New password must not be empty.')
            return
        if new != confirm:
            self._error('New passwords do not match.')
            return

        new_salt = crypto.generate_salt()
        new_key = self.app.derive_key(new, new_salt)

        def reencrypt(blob: bytes) -> bytes:
            return crypto.encrypt(new_key, crypto.decrypt(old_key, blob))

        try:
            self.app.vault.rekey(
                new_salt=new_salt,
                new_verification_blob=crypto.make_verification_blob(new_key),
                reencrypt=reencrypt,
            )
        except Exception:
            # rekey rolled back; the old password still works.
            self._error('Re-key failed. Vault unchanged; old password still works.')
            return

        self.app.key = new_key
        self.app.salt = new_salt
        self.app.reset_key_timer()
        self.notify('Master password changed.')
        self.dismiss(True)
