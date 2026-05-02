from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest, TokenResponse, UserResponse

settings = get_settings()
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(
    request: Request,
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    email_norm = req.email.lower().strip()

    existing = await db.execute(select(User).where(User.email == email_norm))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=email_norm,
        password_hash=hash_password(req.password),
        role=UserRole.USER.value,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    audit("auth.register", user_id=user.id, target_type="user", target_id=user.id)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Log in and receive a JWT bearer token.

    Note: per the OAuth2 password flow spec, the form field is named `username`,
    but TrustMedia treats this field as the user's email address. This is the
    standard convention and lets Swagger's "Authorize" button work out of the box.
    """
    email_norm = (form.username or "").lower().strip()

    result = await db.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        audit("auth.login.failed", target_type="email", target_id=email_norm)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(sub=str(user.id))
    audit("auth.login.success", user_id=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiry_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
