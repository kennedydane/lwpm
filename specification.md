### **Finalized Specification: lwpm (Lightweight Password Manager)**

A single-user, local, terminal-based password manager. All data lives in one encrypted
SQLite file on the user's machine. There is no network, sync, or server component.

#### **1. Architecture & Tech Stack**

* **Language:** Python 3.10+
* **UI:** `textual`
* **Storage:** `sqlite3` (Standard library)
* **Cryptography:**
  * `cryptography.fernet` (AES-128-CBC + HMAC-SHA256 for authenticated encryption).
  * `cryptography.hazmat.primitives.kdf.argon2` (Argon2id) for key derivation.
* **Clipboard:** `pyperclip`
* **Randomness:** `secrets` (CSPRNG) for all password/passphrase generation.
* **Bundled asset:** the EFF large wordlist (7776 words) shipped with the package, used
  by the diceware generator.

#### **2. SQLite Database Schema**

The database is a single local file (default `~/.lwpm.db`). It has two tables: one for
vault configuration (to derive and verify the master key) and one for credentials.

**Table: `config`**
*(Stores the cryptographic parameters needed to reconstruct the key. Does NOT store the
password itself.)*

* `id` (INTEGER PRIMARY KEY)
* `salt` (BLOB): Random bytes combined with the master password to derive the key.
* `verification_blob` (BLOB): A known constant (e.g. `"lwpm-auth-ok"`) encrypted with the
  master key. Used to test whether an entered password is correct.

**Table: `credentials`**

* `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
* `name` (TEXT UNIQUE NOT NULL): The **plaintext** identifier (e.g. `"github"`,
  `"router"`). Kept plaintext to support SQL `ORDER BY`, uniqueness, and fast filtering.
* `secret_blob` (BLOB NOT NULL): A single Fernet-encrypted JSON object holding all secret
  fields for the entry.
* `created_at` (TEXT): ISO-8601 timestamp (plaintext, non-secret).
* `updated_at` (TEXT): ISO-8601 timestamp (plaintext, non-secret).

**Decrypted shape of `secret_blob`** (UTF-8 JSON, optional keys omitted when empty):

```json
{
  "password": "required-string",
  "username": "optional-string",
  "url": "optional-string",
  "notes": "optional-string"
}
```

Only `password` is required. `username`, `url`, and `notes` are optional.

> **Privacy note:** Entry **names** are stored in plaintext. Anyone with read access to
> the `.lwpm.db` file can see *which* services have entries, but not any usernames,
> passwords, URLs, or notes. Encrypting names is explicitly out of scope for v1.

#### **3. Cryptographic Flow**

**Key derivation (Argon2id):**

1. The master key is derived from `(master_password, salt)` via Argon2id, producing 32
   bytes.
2. The 32-byte output is `urlsafe_base64`-encoded to form the Fernet key.
3. Recommended cost parameters (tune to ~0.5–1s on target hardware):
   `time_cost=3`, `memory_cost=64*1024` (64 MiB), `parallelism=4`, `length=32`.

**First-run / vault initialization:**

1. Prompt the user to set a master password.
2. Generate a random `salt`, derive the key, encrypt the verification constant, and
   store `salt` + `verification_blob` in `config`.

**Unlock:**

1. Read `salt` from `config`, derive a candidate key from the entered password.
2. Attempt `Fernet(key).decrypt(verification_blob)`. Success ⇒ correct password; the key
   is held in app memory. Failure (raises `InvalidToken`) ⇒ reject and re-prompt.

**Decode / copy (e.g. user highlights `"github"` and presses `c`):**

1. `SELECT secret_blob FROM credentials WHERE name = ?`.
2. Confirm the master key is in memory (otherwise force re-auth).
3. `json.loads(Fernet(key).decrypt(secret_blob))` → fields dict.
4. Copy the requested field to the clipboard via `pyperclip` (password for `c`, username
   for `u`).
5. Show a temporary Toast: *"Password copied. Clipboard clears in 30s."*

**Change master password:**

1. Verify the *current* master password (re-derive + decrypt `verification_blob`).
2. Prompt for and confirm the *new* master password.
3. Generate a new `salt`, derive the new key.
4. In a **single SQLite transaction**: decrypt every `secret_blob` with the old key and
   re-encrypt it with the new key; re-encrypt the `verification_blob`; update `config`'s
   `salt` and `verification_blob`.
5. On commit, swap the in-memory key to the new key. On any error, roll back so the vault
   stays usable with the old password.

#### **4. State & Memory Management (The Timers)**

* **The 5-Minute Master-Key Timer:**
  * On successful unlock, the derived key is stored in a variable in the Textual App
    state. It exists **only** in memory — never written to disk.
  * A `textual.Timer` is started for 300 seconds.
  * **Reset:** Any keystroke or interaction within the app resets this timer.
  * **Locking:** When the timer fires (or the user presses `l`), the key variable is
    explicitly overwritten (`self.key = None`) and the Authentication screen is pushed
    onto the stack, hiding the vault.

* **The 30-Second Clipboard Timer:**
  * When a value is copied, an independent `textual.Timer` is started for 30 seconds.
  * When it fires, `pyperclip.copy("")` clears the clipboard.
  * Copying a new value resets/replaces the active clipboard timer.

#### **5. Password Generator**

The generator is available inside the Add/Edit modal and supports **two user-selectable
modes**. All randomness uses the `secrets` module.

* **Diceware passphrase mode (default):**
  * Selects N random words from the bundled EFF large wordlist (7776 words).
  * Default **7 words**, joined by a hyphen (e.g. `correct-horse-battery-staple-...`).
  * Word count is adjustable in the modal.

* **Random character mode:**
  * Default length **20**.
  * Toggleable character classes: lowercase, uppercase, digits, symbols (all on by
    default). At least one class must be enabled.
  * Length is adjustable in the modal.

* **Controls in the modal:**
  * A toggle (e.g. a `Select`/radio) switches between the two modes.
  * Hotkey `g`: regenerate using the current mode + settings, populating the password
    input.

#### **6. Textual UI Layout & Flow**

* **View 1: Authentication Screen**
  * A minimalist screen: a `Label` (`"Enter Master Password"`) and an `Input`
    (`password=True`) to mask typing. On first run, this screen runs the
    initialization flow (set + confirm a new master password) instead.

* **View 2: The Vault (Main Screen)**
  * **Header:** App name and a lock icon.
  * **Left Pane (~1/3 width):**
    * A `ListView`/`OptionList` of entry `name`s (`SELECT name FROM credentials ORDER BY
      name`).
    * A search/filter `Input` (toggled with `/`): typing filters the list in real time
      (case-insensitive substring match on `name`).
  * **Right Pane (~2/3 width):** A detail view for the selected entry showing `name`,
    `username`, `url`, and `notes`. The password is shown masked (e.g. `••••••••`) and is
    only ever placed on the clipboard, never rendered in plaintext.
  * **Footer hotkeys:**
    * `a`: add entry
    * `e`: edit selected entry
    * `d`: delete selected entry (with confirmation)
    * `c`: copy selected entry's password
    * `u`: copy selected entry's username
    * `/`: focus search/filter
    * `l`: lock vault
    * `q`: quit

* **View 3: Add / Edit Modal Screen**
  * Inputs: `Name` (required), `Username` (optional), `Password` (required),
    `URL` (optional), `Notes` (optional, multi-line).
  * Generator controls (Section 5), with `g` to regenerate into the `Password` input.
  * **Save:** assemble the non-empty optional fields + password into a JSON object,
    encrypt with the active in-memory key, and `INSERT` (add) or `UPDATE` (edit) the
    `credentials` row; set `created_at`/`updated_at` accordingly. `name` uniqueness is
    enforced by the schema; a clash surfaces a validation error.
  * In **edit** mode the modal is pre-populated from the decrypted entry.

* **View 4: Change Master Password Modal**
  * Inputs: current password, new password, confirm new password.
  * On submit, runs the change-master-password flow from Section 3.

#### **7. Out of Scope (v1)**

* Export / import / encrypted backup files.
* Encrypting entry names (metadata).
* Multiple vaults, profiles, or accounts.
* Any network, sync, or browser-extension integration.

#### **8. Testing Notes**

Tests use `pytest`. Target areas:

* **Crypto round-trip:** encrypt → decrypt of `secret_blob` JSON yields the original
  fields; tampered ciphertext raises `InvalidToken`.
* **KDF & verification:** correct password unlocks; wrong password is rejected;
  first-run initialization produces a verifiable vault.
* **Change master password:** all entries decrypt under the new key afterward; a failure
  mid-operation rolls back and leaves the old password working.
* **Generator:** diceware produces the requested word count from the wordlist; random
  mode honors length and enabled character classes; both draw from `secrets`.
* **DB CRUD:** add/edit/delete and `name` uniqueness behave correctly; search filtering
  matches expected entries.
* **Timers/clipboard:** mock `pyperclip` and `textual.Timer` to assert the key is zeroed
  on lock and the clipboard is cleared after 30s.
