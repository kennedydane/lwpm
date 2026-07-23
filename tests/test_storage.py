"""Tests for lwpm.storage — the SQLite vault.

Storage owns the schema and all SQL. It never holds the master key: re-keying
is driven by a caller-supplied re-encrypt callable so the crypto layer stays
separate (specification.md §2, §3).
"""

import pytest

from lwpm.storage import AlreadyInitializedError, DuplicateNameError, Vault


@pytest.fixture
def vault():
    v = Vault(':memory:')
    try:
        yield v
    finally:
        v.close()


@pytest.fixture
def init_vault(vault):
    vault.initialize(salt=b'salt-1234567890a', verification_blob=b'verif')
    return vault


def add(vault, name, blob=b'blob', created='2026-01-01T00:00:00', updated='2026-01-01T00:00:00'):
    vault.add_credential(name, blob, created_at=created, updated_at=updated)


class TestInitialization:
    def test_new_vault_is_not_initialized(self, vault):
        assert vault.is_initialized() is False

    def test_initialize_then_is_initialized(self, vault):
        vault.initialize(salt=b's' * 16, verification_blob=b'v')
        assert vault.is_initialized() is True

    def test_get_config_returns_salt_and_blob(self, vault):
        vault.initialize(salt=b's' * 16, verification_blob=b'v-blob')
        salt, verification_blob = vault.get_config()
        assert salt == b's' * 16
        assert verification_blob == b'v-blob'

    def test_initialize_twice_raises(self, vault):
        vault.initialize(salt=b's' * 16, verification_blob=b'v')
        with pytest.raises(AlreadyInitializedError):
            vault.initialize(salt=b's' * 16, verification_blob=b'v')


class TestCrud:
    def test_add_and_get_secret_blob(self, init_vault):
        add(init_vault, 'github', b'secret-blob')
        assert init_vault.get_secret_blob('github') == b'secret-blob'

    def test_get_credential_returns_fields_and_timestamps(self, init_vault):
        add(
            init_vault, 'github', b'b', created='2026-01-01T00:00:00', updated='2026-01-02T00:00:00'
        )
        cred = init_vault.get_credential('github')
        assert cred.name == 'github'
        assert cred.secret_blob == b'b'
        assert cred.created_at == '2026-01-01T00:00:00'
        assert cred.updated_at == '2026-01-02T00:00:00'

    def test_get_missing_credential_returns_none(self, init_vault):
        assert init_vault.get_credential('nope') is None

    def test_add_duplicate_name_raises(self, init_vault):
        add(init_vault, 'github')
        with pytest.raises(DuplicateNameError):
            add(init_vault, 'github')

    def test_update_changes_blob_and_timestamp(self, init_vault):
        add(init_vault, 'github', b'old', updated='2026-01-01T00:00:00')
        init_vault.update_credential('github', secret_blob=b'new', updated_at='2026-02-02T00:00:00')
        cred = init_vault.get_credential('github')
        assert cred.secret_blob == b'new'
        assert cred.updated_at == '2026-02-02T00:00:00'

    def test_update_can_rename(self, init_vault):
        add(init_vault, 'github')
        init_vault.update_credential(
            'github', secret_blob=b'b', updated_at='2026-02-02T00:00:00', new_name='gitlab'
        )
        assert init_vault.get_credential('github') is None
        assert init_vault.get_credential('gitlab') is not None

    def test_rename_to_existing_name_raises(self, init_vault):
        add(init_vault, 'github')
        add(init_vault, 'gitlab')
        with pytest.raises(DuplicateNameError):
            init_vault.update_credential(
                'github', secret_blob=b'b', updated_at='t', new_name='gitlab'
            )

    def test_delete_removes_entry(self, init_vault):
        add(init_vault, 'github')
        init_vault.delete_credential('github')
        assert init_vault.get_credential('github') is None


class TestListingAndSearch:
    def test_list_names_sorted(self, init_vault):
        add(init_vault, 'router')
        add(init_vault, 'github')
        add(init_vault, 'amazon')
        assert init_vault.list_names() == ['amazon', 'github', 'router']

    def test_search_is_case_insensitive_substring(self, init_vault):
        add(init_vault, 'GitHub')
        add(init_vault, 'gitlab')
        add(init_vault, 'amazon')
        assert init_vault.search_names('git') == ['GitHub', 'gitlab']

    def test_search_empty_returns_all(self, init_vault):
        add(init_vault, 'b')
        add(init_vault, 'a')
        assert init_vault.search_names('') == ['a', 'b']


class TestRekey:
    def test_reencrypts_every_blob_and_updates_config(self, init_vault):
        add(init_vault, 'a', b'AAA')
        add(init_vault, 'b', b'BBB')

        # Re-encrypt = append a marker so we can observe the transform applied.
        init_vault.rekey(
            new_salt=b'new-salt-16bytes',
            new_verification_blob=b'new-verif',
            reencrypt=lambda blob: blob + b'-rk',
        )

        assert init_vault.get_secret_blob('a') == b'AAA-rk'
        assert init_vault.get_secret_blob('b') == b'BBB-rk'
        salt, verif = init_vault.get_config()
        assert salt == b'new-salt-16bytes'
        assert verif == b'new-verif'

    def test_rollback_on_failure_leaves_vault_unchanged(self, init_vault):
        add(init_vault, 'a', b'AAA')
        add(init_vault, 'b', b'BBB')

        calls = {'n': 0}

        def failing_reencrypt(blob):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('boom on second entry')
            return blob + b'-rk'

        with pytest.raises(RuntimeError):
            init_vault.rekey(
                new_salt=b'new-salt-16bytes',
                new_verification_blob=b'new-verif',
                reencrypt=failing_reencrypt,
            )

        # Nothing committed: old blobs and old config intact.
        assert init_vault.get_secret_blob('a') == b'AAA'
        assert init_vault.get_secret_blob('b') == b'BBB'
        salt, verif = init_vault.get_config()
        assert salt == b'salt-1234567890a'
        assert verif == b'verif'
