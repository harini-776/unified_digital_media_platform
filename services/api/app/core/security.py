import hmac
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(sub: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + (expires_delta or timedelta(minutes=settings.jwt_expiry_minutes))
    claims = {"sub": sub, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode + validate a JWT. Raises JWTError on any failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# Stream tokens — short-lived HMAC for <video> tags that can't send Authorization
#
# Token format: "{exp}.{user_id}.{sig}"
#   - exp:     unix timestamp (seconds)
#   - user_id: UUID of the requesting user (carried in the token so verify
#              doesn't need the caller to pass it separately)
#   - sig:     hex(HMAC-SHA256(jwt_secret, f"{video_id}|{user_id}|{exp}"))
# ---------------------------------------------------------------------------

_STREAM_TOKEN_TTL_DEFAULT = 300  # 5 minutes


def _stream_sig(video_id: UUID, user_id: UUID, exp: int) -> str:
    msg = f"{video_id}|{user_id}|{exp}".encode("utf-8")
    return hmac.new(settings.jwt_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def make_stream_token(video_id: UUID, user_id: UUID, ttl_seconds: int = _STREAM_TOKEN_TTL_DEFAULT) -> str:
    exp = int(time.time()) + ttl_seconds
    sig = _stream_sig(video_id, user_id, exp)
    return f"{exp}.{user_id}.{sig}"


class StreamTokenError(Exception):
    """Raised when a stream token is invalid, malformed, or expired."""


def verify_stream_token(token: str, video_id: UUID) -> UUID:
    """Verify a stream token against a given video_id. Returns the embedded user_id.

    Raises StreamTokenError on any failure (malformed, bad signature, expired).
    """
    if not token or not isinstance(token, str):
        raise StreamTokenError("missing token")

    parts = token.split(".")
    if len(parts) != 3:
        raise StreamTokenError("malformed token")

    exp_str, user_id_str, sig = parts
    try:
        exp = int(exp_str)
    except ValueError:
        raise StreamTokenError("malformed exp")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise StreamTokenError("malformed user_id")

    expected = _stream_sig(video_id, user_id, exp)
    if not hmac.compare_digest(expected, sig):
        raise StreamTokenError("bad signature")

    if exp <= int(time.time()):
        raise StreamTokenError("expired")

    return user_id


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "JWTError",
    "make_stream_token",
    "verify_stream_token",
    "StreamTokenError",
]
