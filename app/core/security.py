import hashlib
import hmac
import secrets

KEY_PREFIX = "rag_"


def hash_key(key: str) -> str:
    """SHA-256 is enough for API keys: they are long random strings, not guessable passwords."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Returns (raw key shown once, hash to store)."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return key, hash_key(key)


def keys_match(given: str, expected: str) -> bool:
    """Constant-time comparison of two secrets of any length."""
    return hmac.compare_digest(hash_key(given), hash_key(expected))


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ")
    return None
