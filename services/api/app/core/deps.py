from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token, JWTError
from app.models.user import User, UserRole
from app.models.video import Video

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        claims = decode_token(token)
    except JWTError:
        raise _INVALID_CREDENTIALS

    sub = claims.get("sub")
    if not sub:
        raise _INVALID_CREDENTIALS

    try:
        user_id = UUID(sub)
    except (ValueError, TypeError):
        raise _INVALID_CREDENTIALS

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _INVALID_CREDENTIALS

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


async def assert_video_owner(db: AsyncSession, video_id: UUID, user: User) -> Video:
    """Load a video, asserting the user owns it (or is admin).

    Raises 404 (not 403) on miss to avoid leaking existence via response code.
    Returns the Video so callers don't double-fetch.
    """
    stmt = select(Video).where(Video.id == video_id)
    if user.role != UserRole.ADMIN.value:
        stmt = stmt.where(Video.user_id == user.id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    return video
