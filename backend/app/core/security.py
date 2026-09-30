import hashlib
import hmac
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash("CaseFlow timing-resistant dummy credential")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _password_hash.verify(password, _dummy_password_hash)
        return False
    return _password_hash.verify(password, password_hash)


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_csrf_nonce() -> str:
    return secrets.token_hex(16)


def derive_csrf_token(secret: str, session_token: str, nonce: str) -> str:
    message = f"{session_token}.{nonce}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def csrf_token_matches(received: str | None, expected: str) -> bool:
    return received is not None and hmac.compare_digest(received, expected)
