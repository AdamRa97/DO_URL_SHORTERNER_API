import re
import secrets
import string

ALPHABET = string.ascii_letters + string.digits  # base62: a-z, A-Z, 0-9
_ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_RESERVED = frozenset(
    {"health", "api", "docs", "redoc", "openapi.json", "favicon.ico", "metrics"}
)


def generate_alias(length: int = 7) -> str:
    """Return a cryptographically random base62 code of the given length.

    62^7 ≈ 3.5 trillion combinations — collision rate is negligible at typical volumes.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def validate_custom_alias(alias: str) -> str:
    """Validate and return a user-supplied custom alias.

    Rules:
    - 3–50 characters
    - Only [a-zA-Z0-9_-]
    - Not a reserved path segment

    Raises ValueError with a descriptive message on failure.
    """
    if not (3 <= len(alias) <= 50):
        raise ValueError("Alias must be between 3 and 50 characters.")
    if not _ALIAS_RE.fullmatch(alias):
        raise ValueError(
            "Alias may only contain letters, digits, hyphens (-), and underscores (_)."
        )
    if alias.lower() in _RESERVED:
        raise ValueError(f"'{alias}' is a reserved path and cannot be used as an alias.")
    return alias
