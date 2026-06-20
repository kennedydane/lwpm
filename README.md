# lwpm — Lightweight Password Manager

A single-user, local, terminal-based password manager. All credentials live in
one encrypted SQLite file on your machine — **no network, no sync, no server**.
Your master password never touches the disk, and your secrets never leave your
computer.

Built with [Textual](https://textual.textualize.io/) for the TUI,
[`cryptography`](https://cryptography.io/) for Argon2id + Fernet, and
[`uv`](https://docs.astral.sh/uv/) for packaging. Runs on Python 3.14.

---

## Contents

- [Features](#features)
- [How It Looks](#how-it-looks)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Keybindings](#keybindings)
  - [Choosing a vault file](#choosing-a-vault-file)
- [Password Generator](#password-generator)
- [How It Works](#how-it-works)
  - [Security model](#security-model)
  - [Cryptographic flow](#cryptographic-flow)
  - [Database schema](#database-schema)
  - [The two timers](#the-two-timers)
- [Project Structure](#project-structure)
- [Development](#development)
- [Security Considerations & Limitations](#security-considerations--limitations)
- [Out of Scope (v1)](#out-of-scope-v1)
- [Wordlist & Licensing](#wordlist--licensing)
- [Acknowledgements](#acknowledgements)

---

## Features

- 🔐 **Authenticated encryption** — secrets sealed with Fernet (AES-128-CBC +
  HMAC-SHA256); tampering is detected, not silently ignored.
- 🗝️ **Argon2id key derivation** — a memory-hard KDF (64 MiB, 3 passes) turns
  your master password into the vault key. No password hash is ever stored.
- 🧠 **Key lives in memory only** — never written to disk; explicitly zeroed on
  lock.
- ⏱️ **Auto-lock & auto-clear** — 5-minute idle lock and 30-second clipboard
  wipe, both automatic.
- 🎲 **Built-in generator** — diceware passphrases *or* random-character
  passwords, all sourced from the `secrets` CSPRNG.
- 🔎 **Instant search** — case-insensitive substring filter over entry names.
- 🔄 **Safe master-password rotation** — re-encrypts the entire vault in a single
  transaction that rolls back cleanly on any failure.
- 📦 **Single-file vault** — your whole vault is one portable `~/.lwpm.db` file.
- ⌨️ **Keyboard-driven** — a fast, mouse-optional terminal UI.

## How It Looks

The vault screen is split into a filterable list of entry names (left) and a
detail pane (right). The password is always masked and only ever reaches the
clipboard — never the screen.

```
┌ lwpm ─────────────────────────────────────────────────────────┐
│ search…                                                        │
│┌──────────────┐ ┌───────────────────────────────────────────┐ │
││ amazon       │ │ github                                     │ │
││ github     ◀ │ │                                            │ │
││ router       │ │ Username: octocat                          │ │
││ vpn          │ │ URL:      https://github.com               │ │
││              │ │ Password: ••••••••                         │ │
││              │ │                                            │ │
││              │ │ Notes:                                     │ │
││              │ │ work account                               │ │
│└──────────────┘ └───────────────────────────────────────────┘ │
│ a Add  e Edit  d Delete  c Copy pw  u Copy user  / Search  l … │
└────────────────────────────────────────────────────────────────┘
```

## Requirements

- **Python 3.14.5+**
- **[uv](https://docs.astral.sh/uv/)** for environment and dependency management
- A **clipboard backend** (Linux only — see below)

Runtime dependencies (installed automatically by `uv`):

| Package        | Purpose                                      |
| -------------- | -------------------------------------------- |
| `textual`      | Terminal UI framework                        |
| `cryptography` | Argon2id KDF + Fernet authenticated encryption |
| `pyperclip`    | Cross-platform clipboard access              |

### Linux clipboard backend

`pyperclip` needs a system clipboard tool. Without one, the copy actions
(`c`, `u`) fail at runtime. Install whichever matches your session:

| Session type | Package                |
| ------------ | ---------------------- |
| X11          | `xclip` *or* `xsel`    |
| Wayland      | `wl-clipboard`         |

```bash
# Debian / Ubuntu
sudo apt install xclip          # X11
sudo apt install wl-clipboard   # Wayland
```

macOS and Windows need no extra package (`pbcopy` / native clipboard are used).

## Installation

```bash
# Clone the repository
git clone git@github.com:kennedydane/lwpm.git
cd lwpm

# Create the virtual environment and install everything
uv sync

# Launch
uv run lwpm
```

On **first run** you'll be asked to set (and confirm) a master password — this
initializes the vault. Every subsequent run shows the unlock screen.

> ⚠️ **There is no recovery.** If you forget your master password, your vault is
> unrecoverable by design. There is no backdoor, reset, or hint.

## Usage

1. **First run** — type a master password twice to create the vault.
2. **Unlock** — type your master password to derive the key into memory.
3. **Add** an entry with `a`, fill in the fields, optionally press `g` to
   generate a password, then **Save**.
4. **Find** an entry: press `/` and type — the list filters live.
5. **Copy** the password with `c` (or username with `u`); it lands on your
   clipboard and is wiped after 30 seconds.
6. **Lock** instantly with `l`, or just walk away — it auto-locks after 5
   minutes idle.

### Keybindings

**Vault screen**

| Key | Action                                   |
| --- | ---------------------------------------- |
| `a` | Add a new entry                          |
| `e` | Edit the selected entry                  |
| `d` | Delete the selected entry (with confirm) |
| `c` | Copy the password to the clipboard       |
| `u` | Copy the username to the clipboard       |
| `p` | Change the master password               |
| `/` | Toggle the search / filter box           |
| `l` | Lock the vault immediately               |
| `q` | Quit                                     |

**Add / Edit modal**

| Key | Action                                                       |
| --- | ------------------------------------------------------------ |
| `g` | Generate a password using the current generator settings     |
| `Esc` | Cancel without saving                                      |

### Choosing a vault file

The vault defaults to `~/.lwpm.db`. Override it with the `LWPM_DB` environment
variable — handy for a separate work vault or for throwaway testing:

```bash
LWPM_DB=/path/to/work-vault.db uv run lwpm
```

## Password Generator

Available inside the Add/Edit modal, with two user-selectable modes. **All
randomness comes from Python's `secrets` module (CSPRNG)** — never `random`.

**Diceware passphrase (default)**
Picks N random words from the bundled wordlist, joined by hyphens
(e.g. `tower-angering-touting-tufted-nuisances-home-alloyed`). Default **7
words**; the count is adjustable in the modal.

**Random character**
Default length **20**. Four toggleable character classes — lowercase,
uppercase, digits, symbols — all on by default. At least one must stay enabled.
Length is adjustable.

> **Wordlist:** the bundled list (`src/lwpm/data/wordlist.txt`) is derived from
> the system `british-english-small` dictionary, filtered to plain lowercase
> a–z words of 4–9 characters (no apostrophes, proper nouns, or punctuation):
> **~29,770 words ≈ 14.9 bits/word**, so a 7-word passphrase carries roughly
> **104 bits** of entropy. See [Wordlist & Licensing](#wordlist--licensing).

## How It Works

### Security model

- Your **master password is never stored**. It is run through Argon2id to derive
  a 32-byte key, which is base64-encoded into a Fernet key and held **only in
  memory**.
- Correctness is checked by decrypting a small **verification blob** (the
  constant `lwpm-auth-ok` encrypted under the key) — not by comparing any stored
  hash.
- Each entry's secret fields (`password`, plus optional `username`, `url`,
  `notes`) are packed into one JSON object and stored as a single
  **Fernet-encrypted blob**. Empty optional fields are omitted.
- **Entry *names* are stored in plaintext.** This is a deliberate trade-off: it
  enables fast SQL `ORDER BY`, uniqueness, and substring search. Anyone who can
  read your `.lwpm.db` sees *which* services you have entries for — but nothing
  else (no usernames, passwords, URLs, or notes).

### Cryptographic flow

```
master password ──┐
                  ▼
          Argon2id(salt, t=3, m=64 MiB, p=4, len=32)
                  │
                  ▼
        urlsafe-base64  ──►  Fernet key (in memory only)
                  │
        ┌─────────┴───────────┐
        ▼                     ▼
 verify "lwpm-auth-ok"   encrypt/decrypt each entry's
 (unlock check)          JSON secret blob
```

**First run:** generate a random 16-byte salt, derive the key, encrypt the
verification constant, and store `salt` + `verification_blob` in `config`.

**Unlock:** read the salt, derive a candidate key, try to decrypt the
verification blob. Success ⇒ correct password (key kept in memory); failure
(`InvalidToken`) ⇒ rejected.

**Change master password:** verify the current password, derive a fresh key from
a new salt, then in **one SQLite transaction** re-encrypt every secret blob and
the verification blob and swap the config. Any error rolls the whole thing back,
leaving the old password working.

### Database schema

A single SQLite file with two tables:

```sql
-- crypto parameters; never the password itself
CREATE TABLE config (
    id                INTEGER PRIMARY KEY,
    salt              BLOB NOT NULL,   -- per-vault Argon2id salt
    verification_blob BLOB NOT NULL    -- "lwpm-auth-ok" encrypted under the key
);

CREATE TABLE credentials (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,  -- PLAINTEXT identifier (e.g. "github")
    secret_blob BLOB NOT NULL,         -- Fernet-encrypted JSON of the secrets
    created_at  TEXT,                  -- ISO-8601, plaintext
    updated_at  TEXT                   -- ISO-8601, plaintext
);
```

Decrypted shape of `secret_blob` (optional keys omitted when empty):

```json
{ "password": "required", "username": "optional", "url": "optional", "notes": "optional" }
```

### The two timers

| Timer                | Duration | Trigger        | Effect                                   |
| -------------------- | -------- | -------------- | ---------------------------------------- |
| Idle auto-lock       | 300 s    | any keystroke resets it | zeroes the in-memory key, returns to the auth screen |
| Clipboard auto-clear | 30 s     | a copy starts/replaces it | runs `pyperclip.copy("")` to wipe the clipboard |

## Project Structure

```
lwpm/
├── pyproject.toml            # uv project: deps, console script, pytest/coverage config
├── uv.lock                   # pinned, reproducible dependency set
├── specification.md          # the frozen v1 spec this implementation follows
├── CLAUDE.md                 # guidance for AI assistants working in the repo
├── src/lwpm/
│   ├── crypto.py             # Argon2id derivation, Fernet, verification blob
│   ├── storage.py            # SQLite vault: schema, CRUD, atomic re-key
│   ├── generator.py          # diceware + random-character generation
│   ├── app.py                # Textual App: timers, clipboard, main() entry point
│   ├── lwpm.tcss             # Textual stylesheet
│   ├── data/wordlist.txt     # bundled diceware wordlist (~29,770 words)
│   └── screens/
│       ├── auth.py           # unlock + first-run initialization
│       ├── vault.py          # entry list + detail pane (main screen)
│       ├── entry_modal.py    # add / edit, with generator controls
│       ├── change_password_modal.py
│       └── confirm.py        # reusable yes/no dialog
└── tests/                    # pytest suite (see Development)
```

### Module responsibilities

| Module           | Responsibility                                                  |
| ---------------- | --------------------------------------------------------------- |
| `lwpm.crypto`    | Argon2id key derivation, Fernet encrypt/decrypt, verification blob — pure functions, no DB or UI |
| `lwpm.storage`   | SQLite schema, CRUD, search, and the atomic re-key transaction — holds **no** key |
| `lwpm.generator` | Diceware and random-character generation, all via `secrets`     |
| `lwpm.app`       | Textual `App`: the only place the key lives; owns both timers and clipboard |
| `lwpm.screens.*` | Auth, Vault, Add/Edit modal, Change-password modal, Confirm dialog |

The layering is deliberate: `crypto` knows nothing about storage, and `storage`
knows nothing about crypto (re-keying is driven by a caller-supplied re-encrypt
callback). The master key lives **only** in `app`.

## Development

```bash
uv sync                 # set up venv + install dev dependencies

uv run pytest           # run the whole suite
uv run pytest -q tests/test_crypto.py::TestDeriveKey   # one class
uv run pytest --cov=lwpm --cov-report=term-missing     # with coverage
```

The suite is **60 tests** (currently ~**87%** coverage, with the
security-critical core at ~100%):

| File                  | Tests | Focus                                                   |
| --------------------- | ----- | ------------------------------------------------------- |
| `test_crypto.py`      | 19    | KDF determinism, round-trip, tamper detection, verification |
| `test_storage.py`     | 17    | CRUD, name uniqueness, search, **re-key + rollback**    |
| `test_generator.py`   | 13    | word count, length, char classes, sourced from `secrets`, bundled list |
| `test_app.py`         | 11    | Textual `Pilot` smoke tests: init/unlock, add, copy, lock, change-pw |

Testing notes:
- Core logic is built test-first (TDD); UI screens are covered by Textual
  `Pilot` smoke tests.
- Tests use cheap Argon2id parameters so derivation is near-instant; the real
  defaults are tuned to ~0.5–1 s.
- The clipboard is exercised by mocking `pyperclip`, so the suite needs no
  clipboard backend.

## Security Considerations & Limitations

- **Plaintext entry names** are an accepted metadata leak (see
  [Security model](#security-model)). Encrypting names is out of scope for v1.
- **Best-effort key zeroing.** Python `bytes` are immutable, so `self.key = None`
  on lock drops the reference but cannot guarantee the bytes are scrubbed from
  memory. This matches the spec's intent within Python's constraints.
- **No protection against a compromised machine.** A keylogger, memory scraper,
  or malicious clipboard manager on your box can still capture secrets while the
  vault is unlocked. lwpm protects the *data at rest*, not a hostile OS.
- **Synchronous key derivation.** Argon2id runs on the UI thread, so unlock,
  first-run, and re-key briefly block (~0.5–1 s) — expected, not a hang.
- **No recovery path.** A forgotten master password means an unrecoverable
  vault.
- **Back up the file yourself.** lwpm has no built-in backup; copy `~/.lwpm.db`
  somewhere safe if it matters to you.

## Out of Scope (v1)

By design, v1 does **not** include: export/import or encrypted backup files,
encrypted entry names, multiple vaults/profiles, or any network, sync, or
browser-extension integration.

## Wordlist & Licensing

The project itself does not yet ship a `LICENSE` file — add one before
distributing.

⚠️ **Note on the bundled wordlist:** `src/lwpm/data/wordlist.txt` is derived from
the GPL-licensed `british-english-small` dictionary (a descendant of SCOWL).
Redistributing words derived from it may carry GPL implications. If you intend
to distribute lwpm under a permissive license, consider swapping in the
[EFF large wordlist](https://www.eff.org/dice) (CC-BY-3.0, 7776 words), which the
original specification called for — it is a drop-in replacement.

## Acknowledgements

- [Textual](https://textual.textualize.io/) — the TUI framework.
- [pyca/cryptography](https://cryptography.io/) — Argon2id and Fernet.
- [EFF](https://www.eff.org/dice) — for popularizing diceware passphrases.
- [SCOWL / `wbritish`](http://wordlist.aspell.net/) — source of the bundled
  wordlist.
