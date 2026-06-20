# lwpm — Lightweight Password Manager

A single-user, local, terminal-based password manager. All credentials live in one encrypted SQLite file on your machine — no network, no sync, no server.

## Security Model

When you unlock the vault, your master password is run through **Argon2id** (time_cost=3, memory_cost=64 MiB, parallelism=4) with a random per-vault salt to produce a 32-byte Fernet key. That key is held in memory only — it is never written to disk. Every secret (password, username, URL, notes) is packed into a JSON object and stored as a single **Fernet-encrypted blob** (AES-128-CBC + HMAC-SHA256) per credential row.

**Privacy trade-off:** entry *names* (e.g. `github`, `router`) are stored in plaintext to allow fast SQL filtering and ordering. Anyone who can read your `.lwpm.db` file will see which services have entries, but nothing else. This is by design in v1.

Two independent timers enforce short-lived secrets:

- **5-minute idle auto-lock** — any interaction resets the timer; when it fires, the in-memory key is zeroed and the auth screen is pushed.
- **30-second clipboard auto-clear** — after copying a password or username, `pyperclip.copy("")` fires 30 seconds later. Copying again resets the timer.

## Install & Run

```bash
# Clone and set up the environment
git clone <repo-url> && cd lwpm
uv sync

# Launch the TUI
uv run lwpm
```

The vault file defaults to `~/.lwpm.db`. To use a different path (useful for testing or maintaining a separate vault):

```bash
LWPM_DB=/path/to/vault.db uv run lwpm
```

On first run you will be prompted to set a master password. Subsequent runs show the unlock screen.

## Linux Clipboard Backend

`pyperclip` requires a clipboard backend. Without one, copy actions (`c`, `u`) will fail with a runtime error. Install one of the following before running:

| Session type | Package |
|---|---|
| X11 | `xclip` or `xsel` |
| Wayland | `wl-clipboard` |

```bash
# Debian/Ubuntu examples
sudo apt install xclip          # X11
sudo apt install wl-clipboard   # Wayland
```

## Keybindings

### Vault screen

| Key | Action |
|---|---|
| `a` | Add new entry |
| `e` | Edit selected entry |
| `d` | Delete selected entry (with confirmation) |
| `c` | Copy password to clipboard |
| `u` | Copy username to clipboard |
| `p` | Change master password |
| `/` | Focus search / filter |
| `l` | Lock vault immediately |
| `q` | Quit |

### Add / Edit modal

| Key | Action |
|---|---|
| `g` | Generate a new password using the current generator settings |

## Password Generator

The generator is available inside the Add/Edit modal and supports two modes:

**Diceware passphrase (default)** — selects N random words from the bundled wordlist, joined by hyphens. Default is 7 words. Word count is adjustable.

**Random character** — default length 20. All character classes (lowercase, uppercase, digits, symbols) are enabled by default; each is individually toggleable. At least one class must remain active. Length is adjustable.

All randomness uses Python's `secrets` module (CSPRNG).

> **Wordlist:** The bundled list (`src/lwpm/data/wordlist.txt`) is derived from the system `british-english-small` dictionary, filtered to plain lowercase a–z words of 4–9 characters (no apostrophes, proper nouns, or punctuation) — ~29,770 words, giving ≈14.9 bits per word (a 7-word passphrase ≈ 104 bits).

## Development

```bash
# Install all dependencies including dev extras
uv sync

# Run the full test suite
uv run pytest

# Run a specific test module or class
uv run pytest tests/test_crypto.py::TestDeriveKey -q

# Run with coverage
uv run pytest --cov
```

### Module layout

| Module | Responsibility |
|---|---|
| `lwpm.crypto` | Argon2id key derivation, Fernet encrypt/decrypt, verification blob |
| `lwpm.storage` | SQLite schema, CRUD, and the atomic re-key transaction |
| `lwpm.generator` | Diceware and random-character password generation |
| `lwpm.app` | Textual `App` subclass, timers, clipboard management, `main()` entry point |
| `lwpm.screens.*` | Auth, Vault, Add/Edit modal, Change-password modal, Confirm dialog |

## Out of Scope (v1)

No export/import, no encrypted entry names, no multiple vaults, no network or sync.
