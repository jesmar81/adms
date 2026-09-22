"""Rotation-ready encryption and keyed lookup for high-risk HR identifiers."""

from __future__ import annotations

from hashlib import sha256
from hmac import new as hmac_new

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings


class PiiEncryptionUnavailableError(RuntimeError):
    """Raised when the deployment did not configure a valid encryption key."""


def _fernet() -> MultiFernet:
    keys = get_settings().hr_pii_encryption_keys()
    if not keys:
        raise PiiEncryptionUnavailableError("HR PII encryption key is not configured")
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except (TypeError, ValueError) as exc:
        raise PiiEncryptionUnavailableError("HR PII encryption key is invalid") from exc


def _lookup_key() -> bytes:
    settings = get_settings()
    configured = settings.hr_pii_lookup_key.strip()
    if configured:
        return configured.encode()
    # Compatibility bridge for existing deployments. A separate secret is
    # strongly preferred, but the derived domain-separated key prevents the
    # old unkeyed digest from remaining a dictionary-attack oracle.
    keys = settings.hr_pii_encryption_keys()
    if not keys:
        raise PiiEncryptionUnavailableError("HR PII lookup key is not configured")
    return sha256(("adms:hr-pii:lookup:" + keys[0]).encode()).digest()


def normalize_identifier(value: str) -> str:
    return "".join(value.upper().split())


def encrypt_identifier(value: str) -> tuple[str, str]:
    normalized = normalize_identifier(value)
    digest = hmac_new(_lookup_key(), normalized.encode(), sha256).hexdigest()
    return _fernet().encrypt(normalized.encode()).decode(), digest


def decrypt_identifier(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise PiiEncryptionUnavailableError("HR PII ciphertext cannot be decrypted") from exc
