"""Pilot-based smoke tests for the lwpm Textual UI.

Each test covers one behaviour, follows Arrange-Act-Assert, and uses fast KDF
parameters so Argon2id derivation is near-instant.  The EFF wordlist is absent
by design; diceware is never called here.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input, ListView

from lwpm.app import LwpmApp
from lwpm.screens.auth import AuthScreen
from lwpm.screens.vault import VaultScreen

# Fast Argon2id params: iterations=1, memory_cost=32 (≥8×lanes), lanes=4
FAST_KDF = {"iterations": 1, "memory_cost": 32, "lanes": 4}
MASTER_PW = "correct-horse-battery-staple"
WRONG_PW = "definitely-wrong-password"
ENTRY_NAME = "github"
ENTRY_PW = "s3cr3t-entry-pw"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> LwpmApp:
    """Return a fresh in-memory app with cheap KDF params."""
    app = LwpmApp(db_path=":memory:")
    app.kdf_params = FAST_KDF
    return app


async def _initialize(pilot) -> None:
    """Fill in password + confirm on the first-run AuthScreen and submit."""
    app = pilot.app
    # Widgets live inside the current screen, not the app root.
    pw_input = app.screen.query_one("#password", Input)
    confirm_input = app.screen.query_one("#confirm", Input)
    pw_input.value = MASTER_PW
    confirm_input.value = MASTER_PW
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


# ---------------------------------------------------------------------------
# Test 1: First-run initialization + unlock
# ---------------------------------------------------------------------------


async def test_first_run_initialization_unlocks_to_vault_screen():
    """
    Filling #password and #confirm with the same value and submitting should
    initialize the vault, derive the key into memory, and switch to VaultScreen.
    """
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Confirm input is visible on first run
        assert isinstance(app.screen, AuthScreen)

        await _initialize(pilot)

        assert app.vault.is_initialized(), "vault should be initialized"
        assert app.key is not None, "key should be held in memory"
        assert isinstance(app.screen, VaultScreen), "should have switched to VaultScreen"


# ---------------------------------------------------------------------------
# Test 2: Wrong password is rejected; correct password then unlocks
# ---------------------------------------------------------------------------


async def test_wrong_password_rejected_then_correct_unlocks():
    """
    After initialization and an explicit lock, submitting the wrong password
    must leave the app locked (key=None, still on AuthScreen). The correct
    password must then unlock successfully.
    """
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Initialize
        await _initialize(pilot)
        assert app.key is not None

        # Lock manually — switches back to AuthScreen
        app.lock()
        await pilot.pause()

        assert isinstance(app.screen, AuthScreen)
        assert app.key is None

        # Enter the wrong password
        pw_input = app.screen.query_one("#password", Input)
        pw_input.value = WRONG_PW
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.key is None, "wrong password must not unlock the vault"
        assert isinstance(app.screen, AuthScreen), "must stay on AuthScreen after wrong pw"

        # Now enter the correct password
        pw_input = app.screen.query_one("#password", Input)
        pw_input.value = MASTER_PW
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.key is not None, "correct password should unlock the vault"
        assert isinstance(app.screen, VaultScreen), "should switch to VaultScreen on unlock"


# ---------------------------------------------------------------------------
# Test 3: Adding an entry makes it appear in the vault list
# ---------------------------------------------------------------------------


async def test_add_entry_appears_in_list_and_storage():
    """
    Opening the EntryModal via 'a', filling #name and #password, then clicking
    #save should persist the entry in the vault and show it in the ListView.
    """
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        vault_screen = app.screen
        assert isinstance(vault_screen, VaultScreen)

        # Open the add modal by calling the action directly.
        # Key presses go to the focused widget (the search Input) and are
        # consumed there, so we invoke the binding action directly instead.
        vault_screen.action_add()
        await pilot.pause()

        # app.screen is now the EntryModal pushed on top of the stack.
        from lwpm.screens.entry_modal import EntryModal
        assert isinstance(app.screen, EntryModal), "EntryModal should be on top"

        # Set fields directly on the modal's inputs
        name_input = app.screen.query_one("#name", Input)
        pw_input = app.screen.query_one("#password", Input)
        name_input.value = ENTRY_NAME
        pw_input.value = ENTRY_PW
        await pilot.pause()

        # Trigger save directly — pilot.click("#save") can throw OutOfBounds
        # when the modal exceeds the test terminal height.  Calling _save()
        # exercises exactly the same code path as the button handler.
        app.screen._save()
        await pilot.pause()

        # Back on VaultScreen
        assert isinstance(app.screen, VaultScreen), "should return to VaultScreen after save"

        # Entry is in storage
        assert ENTRY_NAME in app.vault.list_names(), "entry should be persisted in the vault"

        # Entry is visible in the ListView — the VaultScreen._names list mirrors
        # what the ListView shows, and is refreshed after save via the callback.
        vault_screen_after = app.screen
        assert isinstance(vault_screen_after, VaultScreen)
        assert ENTRY_NAME in vault_screen_after._names, (
            "entry name should be in VaultScreen._names after refresh"
        )
        list_view = vault_screen_after.query_one("#names", ListView)
        assert len(list(list_view.children)) > 0, "ListView should have at least one item"


# ---------------------------------------------------------------------------
# Test 4: Copy password sends the correct value to pyperclip
# ---------------------------------------------------------------------------


async def test_copy_password_calls_pyperclip_and_arms_timer(monkeypatch):
    """
    With an entry selected, pressing 'c' should call pyperclip.copy with
    the plaintext password and leave app._clip_timer set to a non-None timer.
    """
    copied: list[str] = []

    monkeypatch.setattr("lwpm.app.pyperclip.copy", lambda val: copied.append(val))

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        # Add an entry directly via the vault so we skip modal interaction
        from lwpm import crypto
        from datetime import datetime

        blob = crypto.encrypt_fields(app.key, {"password": ENTRY_PW})
        now = datetime.now().isoformat(timespec="seconds")
        app.vault.add_credential(ENTRY_NAME, blob, created_at=now, updated_at=now)

        # Refresh the list so the new entry is visible and selected
        vault_screen = app.screen
        assert isinstance(vault_screen, VaultScreen)
        vault_screen.refresh_list()
        await pilot.pause()

        # Call action_copy_password directly — key presses are captured by the
        # focused Input widget before they reach the VaultScreen binding.
        vault_screen.action_copy_password()
        await pilot.pause()

        assert len(copied) >= 1, "pyperclip.copy should have been called"
        assert copied[-1] == ENTRY_PW, (
            f"copied value should be the entry's password; got {copied[-1]!r}"
        )
        assert app._clip_timer is not None, "clipboard timer should be armed after copy"


# ---------------------------------------------------------------------------
# Test 5: lock() zeroes the key and switches to AuthScreen
# ---------------------------------------------------------------------------


async def test_lock_zeroes_key_and_shows_auth_screen():
    """
    Calling app.lock() (or pressing 'l') must set key to None and push
    a fresh AuthScreen onto the screen stack.
    """
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        assert app.key is not None
        vault_screen = app.screen
        assert isinstance(vault_screen, VaultScreen)

        # Lock by calling the action directly — the 'l' key is captured by
        # the focused Input before it reaches the VaultScreen binding.
        vault_screen.action_lock()
        await pilot.pause()

        assert app.key is None, "key must be zeroed after lock"
        assert isinstance(app.screen, AuthScreen), "should be on AuthScreen after lock"


# ---------------------------------------------------------------------------
# Test 6a: clear_clipboard() calls pyperclip.copy("")
# ---------------------------------------------------------------------------


async def test_clear_clipboard_calls_pyperclip_with_empty_string(monkeypatch):
    """
    app.clear_clipboard() must call pyperclip.copy("") to wipe the clipboard.
    """
    copied: list[str] = []
    monkeypatch.setattr("lwpm.app.pyperclip.copy", lambda val: copied.append(val))

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        app.clear_clipboard()
        await pilot.pause()

        assert "" in copied, "clear_clipboard should call pyperclip.copy with empty string"


# ---------------------------------------------------------------------------
# Test 6b: copy_to_clipboard_value arms _clip_timer
# ---------------------------------------------------------------------------


async def test_copy_to_clipboard_value_arms_clip_timer(monkeypatch):
    """
    copy_to_clipboard_value() should set app._clip_timer to a non-None value
    so the clipboard is cleared automatically after CLIP_TIMEOUT seconds.
    """
    monkeypatch.setattr("lwpm.app.pyperclip.copy", lambda val: None)

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        assert app._clip_timer is None, "timer should start as None"

        app.copy_to_clipboard_value("some-secret", "Password")
        await pilot.pause()

        assert app._clip_timer is not None, "copy_to_clipboard_value should arm the clip timer"


# ---------------------------------------------------------------------------
# Helper: add an entry directly through the vault (skips modal interaction)
# ---------------------------------------------------------------------------


def _add_entry(app, name=ENTRY_NAME, fields=None):
    from datetime import datetime

    from lwpm import crypto

    fields = fields or {"password": ENTRY_PW}
    blob = crypto.encrypt_fields(app.key, fields)
    now = datetime.now().isoformat(timespec="seconds")
    app.vault.add_credential(name, blob, created_at=now, updated_at=now)


# ---------------------------------------------------------------------------
# Test 7: Change master password re-encrypts entries and swaps the key (spec §8)
# ---------------------------------------------------------------------------


async def test_change_master_password_reencrypts_entries_and_swaps_key():
    """
    After changing the master password: the in-memory key changes, every stored
    entry still decrypts (under the NEW key), the old password no longer unlocks,
    and the new password does.
    """
    from lwpm import crypto
    from lwpm.screens.change_password_modal import ChangePasswordModal

    new_pw = "brand-new-master-passphrase"
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        _add_entry(app)
        old_key = app.key

        app.screen.action_change_password()
        await pilot.pause()
        assert isinstance(app.screen, ChangePasswordModal)

        app.screen.query_one("#current", Input).value = MASTER_PW
        app.screen.query_one("#new", Input).value = new_pw
        app.screen.query_one("#confirm", Input).value = new_pw
        await pilot.pause()
        app.screen._submit()
        await pilot.pause()

        # Key swapped; entry decrypts under the new in-memory key.
        assert app.key is not None and app.key != old_key
        blob = app.vault.get_secret_blob(ENTRY_NAME)
        assert crypto.decrypt_fields(app.key, blob) == {"password": ENTRY_PW}

        # Old password no longer unlocks; new one does.
        app.lock()
        await pilot.pause()
        app.screen.query_one("#password", Input).value = MASTER_PW
        await pilot.press("enter")
        await pilot.pause()
        assert app.key is None, "old password must not unlock after change"

        app.screen.query_one("#password", Input).value = new_pw
        await pilot.press("enter")
        await pilot.pause()
        assert app.key is not None, "new password should unlock after change"
        assert isinstance(app.screen, VaultScreen)


# ---------------------------------------------------------------------------
# Test 8: Editing an entry updates its fields
# ---------------------------------------------------------------------------


async def test_edit_entry_updates_fields():
    """Editing the selected entry and saving updates the stored secret blob."""
    from lwpm import crypto
    from lwpm.screens.entry_modal import EntryModal

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        _add_entry(app, fields={"password": ENTRY_PW, "username": "old-user"})
        app.screen.refresh_list(select=ENTRY_NAME)
        await pilot.pause()

        app.screen.action_edit()
        await pilot.pause()
        assert isinstance(app.screen, EntryModal)

        app.screen.query_one("#username", Input).value = "new-user"
        await pilot.pause()
        app.screen._save()
        await pilot.pause()

        blob = app.vault.get_secret_blob(ENTRY_NAME)
        assert crypto.decrypt_fields(app.key, blob)["username"] == "new-user"


# ---------------------------------------------------------------------------
# Test 9: Deleting an entry through the confirm modal removes it
# ---------------------------------------------------------------------------


async def test_delete_entry_via_confirm_removes_it():
    """Confirming the delete modal removes the entry from the vault."""
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        _add_entry(app)
        app.screen.refresh_list(select=ENTRY_NAME)
        await pilot.pause()

        app.screen.action_delete()
        await pilot.pause()
        from lwpm.screens.confirm import ConfirmModal

        assert isinstance(app.screen, ConfirmModal)
        # Confirm "yes" — dismissing with True fires the delete callback.
        app.screen.dismiss(True)
        await pilot.pause()

        assert ENTRY_NAME not in app.vault.list_names()


# ---------------------------------------------------------------------------
# Test 10: The 'g' generator populates the password field (random mode)
# ---------------------------------------------------------------------------


async def test_generate_random_password_populates_field():
    """Switching the modal to random mode and generating fills #password.

    Random mode is used because the EFF wordlist (diceware) is not bundled.
    """
    from textual.widgets import Select

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _initialize(pilot)
        await pilot.pause()

        app.screen.action_add()
        await pilot.pause()
        modal = app.screen

        modal.query_one("#gen-mode", Select).value = "random"
        modal.query_one("#gen-length", Input).value = "24"
        await pilot.pause()
        modal.action_generate()
        await pilot.pause()

        assert len(modal.query_one("#password", Input).value) == 24
