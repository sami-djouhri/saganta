"""Verschlüsselung der IMAP/SMTP-Passwörter at-rest.

Klartext-Passwörter in SQLite wären ein DB-Dump-Leak. Wir legen nur Fernet-Ciphertext ab;
der Key kommt aus FERNET_KEY (SOPS-Secret) und verlässt nie die DB. Key-Rotation = alle
Account-Passwörter neu eingeben (bewusst akzeptiert für Stage 1).
"""
from cryptography.fernet import Fernet, InvalidToken

from .config import settings


class CryptoError(RuntimeError):
    pass


def _fernet() -> Fernet:
    try:
        return Fernet(settings.fernet_key.encode())
    except (ValueError, TypeError) as exc:
        raise CryptoError(
            "FERNET_KEY ungültig: 32-Byte urlsafe-base64 erwartet "
            "(Fernet.generate_key())."
        ) from exc


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise CryptoError(
            "Passwort konnte nicht entschlüsselt werden: FERNET_KEY rotiert? "
            "Konto neu verbinden."
        ) from exc
