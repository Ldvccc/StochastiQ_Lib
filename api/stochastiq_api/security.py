import logging
import re
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hache un mot de passe avec argon2id."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: int, secret_key: str, expire_hours: int) -> str:
    """JWT signé (HS256), sujet = identifiant de l'utilisateur."""
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=expire_hours)}
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def decode_token(token: str, secret_key: str) -> int | None:
    """Retourne l'identifiant de l'utilisateur, ou None si le jeton est invalide ou expiré."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


_INVITATION_PATH = re.compile(r"(/invitations/)[^/\s?\"]+")


class MaskInvitationTokens(logging.Filter):
    """Masque les jetons d'invitation présents dans les chemins des journaux d'accès."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _INVITATION_PATH.sub(r"\1***", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        if isinstance(record.msg, str):
            record.msg = _INVITATION_PATH.sub(r"\1***", record.msg)
        return True
