# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**Greenfield.** As of this writing the repository contains only `specification.md` — there is no code, package config, or test suite yet. `specification.md` is the authoritative source of truth for what `lwpm` should be; read it before implementing anything. When you scaffold the project, prefer `uv` for environment/dependency management and `pytest` for tests (see Commands below).

## What This Is

`lwpm` (Lightweight Password Manager) is a **single-user, local, terminal-based** password manager. All data lives in one encrypted SQLite file (default `~/.lwpm.db`) on the user's machine. There is deliberately **no network, sync, or server component** — keep it that way (see spec §7, Out of Scope).

## Tech Stack

- Python 3.10+
- **UI:** `textual` (TUI framework — screens, modals, timers, key bindings)
- **Storage:** `sqlite3` (stdlib)
- **Crypto:** `cryptography` — `fernet.Fernet` for authenticated encryption, `hazmat.primitives.kdf.argon2` (Argon2id) for key derivation
- **Clipboard:** `pyperclip`
- **Randomness:** `secrets` (CSPRNG) for *all* password/passphrase generation — never `random`
- **Bundled asset:** `src/lwpm/data/wordlist.txt` (~29,770 words) for the diceware generator — derived from the system `british-english-small` dictionary, filtered to lowercase a–z words of 4–9 chars. (The spec names the EFF large wordlist; a local dictionary was substituted at build time.)

## Architecture & Critical Invariants

The design hinges on a few cross-cutting rules that aren't obvious from any single file. Get these wrong and you break the security model.

### The master key lives only in memory
- The master password is **never** stored. Argon2id derives a 32-byte key from `(master_password, salt)`; that key is base64-url-encoded into a Fernet key and held in Textual app state (`self.key`).
- Password correctness is verified by decrypting a `verification_blob` (a known constant encrypted under the key) — *not* by storing any hash of the password.
- On lock (5-min idle timer fires, or user presses `l`), explicitly set `self.key = None` and push the Authentication screen. Any keystroke resets the idle timer.

### Encryption boundary: what's plaintext vs. encrypted
- **Plaintext (by design):** entry `name`, `created_at`, `updated_at`, the Argon2 `salt`. Names are plaintext to allow SQL `ORDER BY`, `UNIQUE`, and fast substring filtering. This is a documented privacy trade-off (spec §2) — do not "fix" it for v1.
- **Encrypted:** everything secret (`password`, `username`, `url`, `notes`) is packed into one UTF-8 JSON object and stored as a single Fernet-encrypted `secret_blob`. Optional keys are omitted when empty; only `password` is required.
- Passwords are **only ever placed on the clipboard** — never rendered in plaintext in the UI (detail view shows `••••••••`).

### Two independent timers (don't conflate them)
- **5-min master-key timer** (300s): idle auto-lock; reset on any interaction; zeroes the key.
- **30-sec clipboard timer**: after a copy, clears the clipboard via `pyperclip.copy("")`. Copying again replaces/resets this timer. It is separate from the key timer.

### Change-master-password is a single atomic transaction
Re-keying must happen in **one SQLite transaction**: verify the old password, then decrypt every `secret_blob` with the old key and re-encrypt with the new key, re-encrypt the `verification_blob`, and update `config`'s `salt` + `verification_blob`. On commit, swap the in-memory key. **On any error, roll back** so the vault stays usable under the old password. A partial re-key that loses data is the worst-possible bug here.

### Schema (two tables)
- `config`: `salt` (BLOB), `verification_blob` (BLOB) — the params to reconstruct & verify the key.
- `credentials`: `id`, `name` (TEXT UNIQUE NOT NULL), `secret_blob` (BLOB NOT NULL), `created_at`, `updated_at`.

### UI structure (Textual)
Auth screen → Vault (left pane = filterable `ListView`/`OptionList` of names, right pane = detail) → Add/Edit modal (with the generator) → Change-master-password modal. Footer hotkeys: `a` add, `e` edit, `d` delete (confirm), `c` copy password, `u` copy username, `/` search, `l` lock, `q` quit, `g` regenerate (in modal).

## Commands

No tooling is wired up yet. When scaffolding, use `uv` (not pip directly) and `pytest`:

```bash
uv venv .venv && source .venv/bin/activate
uv pip install textual cryptography pyperclip pytest
uv run pytest                       # run all tests
uv run pytest path/to/test.py::test_name   # run a single test
uv run python -m lwpm               # launch the TUI (once an entry point exists)
```

## Testing Focus (from spec §8)

When implementing, the security-critical test targets are:
- **Crypto round-trip:** `secret_blob` JSON survives encrypt→decrypt; tampered ciphertext raises `InvalidToken`.
- **KDF & verification:** correct password unlocks, wrong password rejected, first-run init produces a verifiable vault.
- **Change master password:** every entry decrypts under the new key; mid-operation failure rolls back and the old password still works.
- **Generator:** diceware yields the requested word count from the wordlist; random mode honors length + enabled character classes; both draw from `secrets`.
- **Timers/clipboard:** mock `pyperclip` and `textual.Timer` to assert the key is zeroed on lock and the clipboard clears after 30s.
