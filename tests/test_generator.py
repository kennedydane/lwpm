"""Tests for lwpm.generator — diceware and random password generation.

All randomness must come from the ``secrets`` CSPRNG (specification.md §5).
The generators accept an injected wordlist so they can be tested without the
bundled EFF file; ``load_wordlist`` reads the bundled file when present.
"""

import string

import pytest

from lwpm import generator

WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]


class TestDiceware:
    def test_default_is_seven_words(self):
        phrase = generator.diceware(wordlist=WORDS)
        assert len(phrase.split("-")) == 7

    def test_respects_word_count(self):
        phrase = generator.diceware(words=4, wordlist=WORDS)
        assert len(phrase.split("-")) == 4

    def test_words_come_from_the_wordlist(self):
        phrase = generator.diceware(words=5, wordlist=WORDS)
        assert all(word in WORDS for word in phrase.split("-"))

    def test_custom_separator(self):
        phrase = generator.diceware(words=3, sep=".", wordlist=WORDS)
        assert len(phrase.split(".")) == 3

    def test_uses_secrets_choice(self, monkeypatch):
        calls = {"n": 0}

        def fake_choice(seq):
            calls["n"] += 1
            return seq[0]

        monkeypatch.setattr(generator.secrets, "choice", fake_choice)
        phrase = generator.diceware(words=3, wordlist=WORDS)
        assert calls["n"] == 3
        assert phrase == "alpha-alpha-alpha"


class TestRandomPassword:
    def test_default_length_is_twenty(self):
        assert len(generator.random_password()) == 20

    def test_respects_length(self):
        assert len(generator.random_password(length=32)) == 32

    def test_only_lowercase(self):
        pw = generator.random_password(
            length=50, lower=True, upper=False, digits=False, symbols=False
        )
        assert all(c in string.ascii_lowercase for c in pw)

    def test_only_digits(self):
        pw = generator.random_password(
            length=50, lower=False, upper=False, digits=True, symbols=False
        )
        assert all(c in string.digits for c in pw)

    def test_only_uppercase(self):
        pw = generator.random_password(
            length=50, lower=False, upper=True, digits=False, symbols=False
        )
        assert all(c in string.ascii_uppercase for c in pw)

    def test_no_classes_enabled_raises(self):
        with pytest.raises(ValueError):
            generator.random_password(
                lower=False, upper=False, digits=False, symbols=False
            )

    def test_uses_secrets_choice(self, monkeypatch):
        calls = {"n": 0}

        def fake_choice(seq):
            calls["n"] += 1
            return seq[0]

        monkeypatch.setattr(generator.secrets, "choice", fake_choice)
        generator.random_password(length=8, upper=False, digits=False, symbols=False)
        assert calls["n"] == 8


class TestLoadWordlist:
    def test_bundled_wordlist_is_large_and_clean(self):
        try:
            words = generator.load_wordlist()
        except FileNotFoundError:
            pytest.skip("bundled wordlist not present yet")
        # A diceware list needs enough words for decent entropy per word.
        assert len(words) >= 4000
        # One plain lowercase a–z word per line — no number column, no
        # whitespace, apostrophes, or capitals.
        assert all(w == w.strip() and w.isalpha() and w.islower() for w in words)
