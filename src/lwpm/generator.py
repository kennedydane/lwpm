"""Password and passphrase generation for lwpm.

Two modes (specification.md §5): a diceware passphrase drawn from the bundled
wordlist, and a random-character password over selectable classes. All
randomness uses the ``secrets`` CSPRNG.

The bundled wordlist is derived from the system ``british-english-small``
dictionary, filtered to plain lowercase a–z words of 4–9 characters (no
apostrophes, proper nouns, or punctuation).
"""

from __future__ import annotations

import secrets
import string
from functools import lru_cache
from importlib import resources

WORDLIST_RESOURCE = "wordlist.txt"

DEFAULT_WORDS = 7
DEFAULT_LENGTH = 20
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?"


@lru_cache(maxsize=1)
def load_wordlist() -> list[str]:
    """Load the bundled wordlist as one plain word per line.

    Raises FileNotFoundError if the wordlist has not been bundled yet.
    """
    resource = resources.files("lwpm.data").joinpath(WORDLIST_RESOURCE)
    if not resource.is_file():
        raise FileNotFoundError(
            f"bundled wordlist {WORDLIST_RESOURCE!r} not found in lwpm.data"
        )
    text = resource.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def diceware(
    words: int = DEFAULT_WORDS,
    *,
    sep: str = "-",
    wordlist: list[str] | None = None,
) -> str:
    """Return a passphrase of ``words`` words joined by ``sep``."""
    pool = wordlist if wordlist is not None else load_wordlist()
    return sep.join(secrets.choice(pool) for _ in range(words))


def random_password(
    length: int = DEFAULT_LENGTH,
    *,
    lower: bool = True,
    upper: bool = True,
    digits: bool = True,
    symbols: bool = True,
) -> str:
    """Return a random password over the enabled character classes.

    At least one class must be enabled, else ValueError is raised.
    """
    alphabet = ""
    if lower:
        alphabet += string.ascii_lowercase
    if upper:
        alphabet += string.ascii_uppercase
    if digits:
        alphabet += string.digits
    if symbols:
        alphabet += SYMBOLS
    if not alphabet:
        raise ValueError("at least one character class must be enabled")
    return "".join(secrets.choice(alphabet) for _ in range(length))
