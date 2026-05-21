from cryptography.fernet import Fernet, InvalidToken
from app.config import settings
import base64
import logging

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    # Fernet requires 32 url-safe base64-encoded bytes
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value using Fernet symmetric encryption."""
    if not plaintext:
        raise ValueError("Cannot encrypt empty value")
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    if not ciphertext:
        raise ValueError("Cannot decrypt empty value")
    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception) as e:
        logger.error("Decryption failed — invalid token or key mismatch")
        raise ValueError("Falha ao descriptografar valor. Chave inválida.") from e


def generate_new_key() -> str:
    """Generate a new Fernet key. Use once and save to .env."""
    return Fernet.generate_key().decode()
