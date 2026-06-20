"""Tests for lwpm.crypto — Argon2id key derivation and Fernet encryption.

These tests cover the security-critical core described in specification.md §3
and §8: key derivation, the verification blob, secret_blob round-tripping, and
tamper detection.
"""

import base64

import pytest
from cryptography.fernet import InvalidToken

from lwpm import crypto

# Fast Argon2id parameters for tests (the real defaults are tuned to ~0.5–1s).
FAST = {"iterations": 1, "memory_cost": 8 * 4, "lanes": 4}


class TestDeriveKey:
    def test_same_password_and_salt_yield_same_key(self):
        salt = b"\x00" * 16
        k1 = crypto.derive_key("hunter2", salt, **FAST)
        k2 = crypto.derive_key("hunter2", salt, **FAST)
        assert k1 == k2

    def test_different_salt_yields_different_key(self):
        k1 = crypto.derive_key("hunter2", b"\x00" * 16, **FAST)
        k2 = crypto.derive_key("hunter2", b"\x01" * 16, **FAST)
        assert k1 != k2

    def test_different_password_yields_different_key(self):
        salt = b"\x00" * 16
        k1 = crypto.derive_key("hunter2", salt, **FAST)
        k2 = crypto.derive_key("hunter3", salt, **FAST)
        assert k1 != k2

    def test_key_is_a_valid_fernet_key(self):
        # A Fernet key is 32 url-safe-base64 bytes -> 44 chars; constructing
        # Fernet(key) must not raise.
        from cryptography.fernet import Fernet

        key = crypto.derive_key("hunter2", b"\x00" * 16, **FAST)
        assert len(base64.urlsafe_b64decode(key)) == 32
        Fernet(key)  # raises if malformed

    def test_default_parameters_match_spec(self):
        # Spec §3: time_cost=3, memory_cost=64 MiB, parallelism=4, length=32.
        assert crypto.DEFAULT_ITERATIONS == 3
        assert crypto.DEFAULT_MEMORY_COST == 64 * 1024
        assert crypto.DEFAULT_LANES == 4


class TestGenerateSalt:
    def test_returns_16_bytes(self):
        assert len(crypto.generate_salt()) == 16

    def test_is_random_each_call(self):
        assert crypto.generate_salt() != crypto.generate_salt()


class TestEncryptDecrypt:
    def setup_method(self):
        self.key = crypto.derive_key("pw", b"\x00" * 16, **FAST)

    def test_round_trip(self):
        blob = crypto.encrypt(self.key, b"secret bytes")
        assert crypto.decrypt(self.key, blob) == b"secret bytes"

    def test_ciphertext_is_not_plaintext(self):
        blob = crypto.encrypt(self.key, b"secret bytes")
        assert b"secret bytes" not in blob

    def test_tampered_ciphertext_raises_invalid_token(self):
        blob = bytearray(crypto.encrypt(self.key, b"secret bytes"))
        blob[-1] ^= 0xFF
        with pytest.raises(InvalidToken):
            crypto.decrypt(self.key, bytes(blob))

    def test_wrong_key_raises_invalid_token(self):
        blob = crypto.encrypt(self.key, b"secret bytes")
        other = crypto.derive_key("pw", b"\x01" * 16, **FAST)
        with pytest.raises(InvalidToken):
            crypto.decrypt(other, blob)


class TestFields:
    def setup_method(self):
        self.key = crypto.derive_key("pw", b"\x00" * 16, **FAST)

    def test_round_trip_all_fields(self):
        fields = {
            "password": "p",
            "username": "u",
            "url": "https://x",
            "notes": "n",
        }
        blob = crypto.encrypt_fields(self.key, fields)
        assert crypto.decrypt_fields(self.key, blob) == fields

    def test_only_password_required(self):
        blob = crypto.encrypt_fields(self.key, {"password": "p"})
        assert crypto.decrypt_fields(self.key, blob) == {"password": "p"}

    def test_empty_optional_fields_are_omitted(self):
        fields = {"password": "p", "username": "", "url": None, "notes": ""}
        blob = crypto.encrypt_fields(self.key, fields)
        assert crypto.decrypt_fields(self.key, blob) == {"password": "p"}

    def test_missing_password_raises(self):
        with pytest.raises(ValueError):
            crypto.encrypt_fields(self.key, {"username": "u"})

    def test_empty_password_raises(self):
        with pytest.raises(ValueError):
            crypto.encrypt_fields(self.key, {"password": ""})


class TestVerification:
    def test_constant_value(self):
        assert crypto.VERIFICATION_CONSTANT == b"lwpm-auth-ok"

    def test_correct_key_verifies(self):
        key = crypto.derive_key("pw", b"\x00" * 16, **FAST)
        blob = crypto.make_verification_blob(key)
        assert crypto.verify_key(key, blob) is True

    def test_wrong_key_does_not_verify(self):
        key = crypto.derive_key("pw", b"\x00" * 16, **FAST)
        wrong = crypto.derive_key("nope", b"\x00" * 16, **FAST)
        blob = crypto.make_verification_blob(key)
        assert crypto.verify_key(wrong, blob) is False
