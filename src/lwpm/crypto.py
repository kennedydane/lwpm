"""Cryptographic core for lwpm.

Pure functions over keys and bytes — no database, no UI, no global state. The
master key is derived from the user's password with Argon2id and used as a
Fernet key (AES-128-CBC + HMAC-SHA256) for authenticated encryption.

See specification.md §3 for the cryptographic flow.
"""

from __future__ import annotations

import base64
import json
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

# Argon2id cost parameters (specification.md §3). Tuned to ~0.5–1s on typical
# hardware. Exposed as overridable defaults so tests can run with cheap params.
DEFAULT_ITERATIONS = 3  # spec "time_cost"
DEFAULT_MEMORY_COST = 64 * 1024  # KiB == 64 MiB
DEFAULT_LANES = 4  # spec "parallelism"
KEY_LENGTH = 32  # bytes; a Fernet key is 32 url-safe-base64 bytes
SALT_BYTES = 16

# A known constant encrypted under the master key. Decrypting it successfully
# proves the entered password derived the right key (specification.md §3).
VERIFICATION_CONSTANT = b"lwpm-auth-ok"

# Optional secret fields; omitted from the stored blob when empty.
_OPTIONAL_FIELDS = ("username", "url", "notes")


def generate_salt() -> bytes:
    """Return a fresh random salt for key derivation."""
    return os.urandom(SALT_BYTES)


def derive_key(
    master_password: str,
    salt: bytes,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    memory_cost: int = DEFAULT_MEMORY_COST,
    lanes: int = DEFAULT_LANES,
) -> bytes:
    """Derive a Fernet key from a master password and salt via Argon2id.

    Returns the 32-byte Argon2id output encoded as url-safe base64, which is
    exactly the format Fernet expects.
    """
    raw = Argon2id(
        salt=salt,
        length=KEY_LENGTH,
        iterations=iterations,
        lanes=lanes,
        memory_cost=memory_cost,
    ).derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt bytes with the Fernet key."""
    return Fernet(key).encrypt(plaintext)


def decrypt(key: bytes, blob: bytes) -> bytes:
    """Decrypt a Fernet token. Raises InvalidToken on wrong key or tampering."""
    return Fernet(key).decrypt(blob)


def encrypt_fields(key: bytes, fields: dict) -> bytes:
    """Encrypt the secret_blob field dict as a single Fernet-encrypted JSON object.

    ``password`` is required and non-empty. Optional fields (username, url,
    notes) are omitted when empty/None, per specification.md §2.
    """
    password = fields.get("password")
    if not password:
        raise ValueError("password is required and must be non-empty")

    payload: dict[str, str] = {"password": password}
    for name in _OPTIONAL_FIELDS:
        value = fields.get(name)
        if value:
            payload[name] = value

    data = json.dumps(payload).encode("utf-8")
    return encrypt(key, data)


def decrypt_fields(key: bytes, blob: bytes) -> dict:
    """Decrypt a secret_blob back into its field dict."""
    return json.loads(decrypt(key, blob).decode("utf-8"))


def make_verification_blob(key: bytes) -> bytes:
    """Encrypt the verification constant under the key."""
    return encrypt(key, VERIFICATION_CONSTANT)


def verify_key(key: bytes, verification_blob: bytes) -> bool:
    """Return True iff the key decrypts the verification blob to the constant."""
    from cryptography.fernet import InvalidToken

    try:
        return decrypt(key, verification_blob) == VERIFICATION_CONSTANT
    except InvalidToken:
        return False
