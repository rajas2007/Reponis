from cryptography.fernet import Fernet

from src.core.config import settings

# Initialize Fernet with the configured key
assert settings.FERNET_KEY is not None, "FERNET_KEY must be set"
_fernet = Fernet(settings.FERNET_KEY)


def encrypt(data: str) -> str:
    """Encrypt a string and return the url-safe base64-encoded encrypted string."""
    return _fernet.encrypt(data.encode("utf-8")).decode("utf-8")


def decrypt(encrypted_data: str) -> str:
    """Decrypt a url-safe base64-encoded string."""
    return _fernet.decrypt(encrypted_data.encode("utf-8")).decode("utf-8")
