"""Add / Edit modal, including the password generator controls."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Switch, TextArea

from lwpm import crypto, generator
from lwpm.storage import DuplicateNameError


class EntryModal(ModalScreen[bool]):
    """Create a new credential or edit an existing one.

    Constructed with no args for *add*, or with ``name`` + decrypted ``fields``
    for *edit*. Persists the entry itself and dismisses with True on save.
    """

    BINDINGS = [
        ('g', 'generate', 'Generate password'),
        ('escape', 'cancel', 'Cancel'),
    ]

    def __init__(self, name: str | None = None, fields: dict | None = None) -> None:
        super().__init__()
        self._original_name = name
        self._fields = fields or {}

    @property
    def is_edit(self) -> bool:
        return self._original_name is not None

    def compose(self) -> ComposeResult:
        f = self._fields
        with Vertical(id='entry-box'):
            yield Label('Edit Entry' if self.is_edit else 'Add Entry', id='entry-title')
            yield Input(value=self._original_name or '', placeholder='name', id='name')
            yield Input(value=f.get('username', ''), placeholder='username', id='username')
            yield Input(
                value=f.get('password', ''),
                placeholder='password',
                password=True,
                id='password',
            )
            yield Input(value=f.get('url', ''), placeholder='url', id='url')
            yield TextArea(f.get('notes', ''), id='notes')

            with Horizontal(id='gen-row'):
                yield Select(
                    [('Diceware', 'diceware'), ('Random', 'random')],
                    value='diceware',
                    allow_blank=False,
                    id='gen-mode',
                )
                yield Input(value='7', type='integer', id='gen-words')
                yield Input(value='20', type='integer', id='gen-length')
            with Horizontal(id='gen-classes'):
                yield Label('a-z')
                yield Switch(value=True, id='cls-lower')
                yield Label('A-Z')
                yield Switch(value=True, id='cls-upper')
                yield Label('0-9')
                yield Switch(value=True, id='cls-digits')
                yield Label('!@#')
                yield Switch(value=True, id='cls-symbols')

            yield Label('', id='entry-error')
            with Horizontal(id='entry-buttons'):
                yield Button('Save', variant='primary', id='save')
                yield Button('Cancel', id='cancel')
                yield Button('Generate (g)', id='generate')

    def on_mount(self) -> None:
        self.query_one('#name', Input).focus()

    # -- helpers --------------------------------------------------------

    def _error(self, message: str) -> None:
        self.query_one('#entry-error', Label).update(message)

    def _int_value(self, widget_id: str, default: int) -> int:
        try:
            return int(self.query_one(widget_id, Input).value)
        except (ValueError, TypeError):
            return default

    # -- generator ------------------------------------------------------

    def action_generate(self) -> None:
        mode = self.query_one('#gen-mode', Select).value
        try:
            if mode == 'diceware':
                password = generator.diceware(words=self._int_value('#gen-words', 7))
            else:
                password = generator.random_password(
                    length=self._int_value('#gen-length', 20),
                    lower=self.query_one('#cls-lower', Switch).value,
                    upper=self.query_one('#cls-upper', Switch).value,
                    digits=self.query_one('#cls-digits', Switch).value,
                    symbols=self.query_one('#cls-symbols', Switch).value,
                )
        except FileNotFoundError:
            self._error('Wordlist not bundled; use Random mode.')
            return
        except ValueError as exc:
            self._error(str(exc))
            return
        self.query_one('#password', Input).value = password

    # -- save / cancel --------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'save':
            self._save()
        elif event.button.id == 'cancel':
            self.dismiss(False)
        elif event.button.id == 'generate':
            self.action_generate()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _save(self) -> None:
        name = self.query_one('#name', Input).value.strip()
        fields = {
            'password': self.query_one('#password', Input).value,
            'username': self.query_one('#username', Input).value.strip(),
            'url': self.query_one('#url', Input).value.strip(),
            'notes': self.query_one('#notes', TextArea).text,
        }
        if not name:
            self._error('Name is required.')
            return
        try:
            blob = crypto.encrypt_fields(self.app.key, fields)
        except ValueError:
            self._error('Password is required.')
            return

        now = datetime.now().isoformat(timespec='seconds')
        try:
            if self.is_edit:
                self.app.vault.update_credential(
                    self._original_name,
                    secret_blob=blob,
                    updated_at=now,
                    new_name=name if name != self._original_name else None,
                )
            else:
                self.app.vault.add_credential(name, blob, created_at=now, updated_at=now)
        except DuplicateNameError:
            self._error(f"An entry named '{name}' already exists.")
            return
        self.dismiss(True)
