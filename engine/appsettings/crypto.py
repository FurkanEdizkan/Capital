"""Symmetric encryption for secrets stored in the database.

Binance (and later LLM) API keys are encrypted at rest with a Fernet key
derived from `CAPITAL_SECRET_KEY`. Without that exact key a database restore
cannot decrypt the stored credentials — back it up separately from the DB.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from config import settings


def _fernet() -> Fernet:
    """Build the Fernet cipher from the configured secret key.

    Any `CAPITAL_SECRET_KEY` string works — it is SHA-256 hashed into the
    32-byte key Fernet requires.
    """
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    """Encrypt `plaintext` to a storable token."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by `encrypt`.

    Raises `ValueError` if the token cannot be decrypted — usually a wrong or
    rotated `CAPITAL_SECRET_KEY`.
    """
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("could not decrypt — wrong CAPITAL_SECRET_KEY?") from exc
