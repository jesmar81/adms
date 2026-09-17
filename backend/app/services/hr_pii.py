"""Encryption helpers for high-risk HR identifiers.

The database stores an authenticated Fernet ciphertext plus a SHA-256 lookup
hash.  Hashes are for duplicate detection only and must never be exposed by
the API.  The key is supplied as ``ZKTECO_HR_PII_ENCRYPTION_KEY``.
"""

from __future__ import annotations

from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class PiiEncryptionUnavailableError(RuntimeError):
    """Raised when the deployment did not configure a valid encryption key."""


def _fernet() -> Fernet:
    key = get_settings().hr_pii_encryption_key.strip()
    if not key:
        raise PiiEncryptionUnavailableError("HR PII encryption key is not configured")
    try:
        return Fernet(key.encode())
    except (TypeError, ValueError) as exc:
        raise PiiEncryptionUnavailableError("HR PII encryption key is invalid") from exc


def normalize_identifier(value: str) -> str:
    return "".join(value.upper().split())


def encrypt_identifier(value: str) -> tuple[str, str]:
    normalized = normalize_identifier(value)
    return _fernet().encrypt(normalized.encode()).decode(), sha256(normalized.encode()).hexdigest()


def decrypt_identifier(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise PiiEncryptionUnavailableError("HR PII ciphertext cannot be decrypted") from exc
