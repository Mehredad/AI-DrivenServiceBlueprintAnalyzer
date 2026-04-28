"""
Auth router — /api/auth/*
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserLogin, TokenRefresh, TokenResponse, UserOut, UserPatch
from app.services import auth_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    if await auth_service.get_user_by_email(db, body.email):
        raise HTTPException(400, "Email already registered")

    user = User(
        email=body.email.lower(),
        password_hash=auth_service.hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()  # assigns id

    access, expires_in = auth_service.create_access_token(user.id, user.role)
    refresh = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_email(db, body.email)
    if not user or not auth_service.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")

    user.last_login = datetime.now(timezone.utc)
    access, expires_in = auth_service.create_access_token(user.id, user.role)
    refresh = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    record = await auth_service.validate_refresh_token(db, body.refresh_token)
    if not record:
        raise HTTPException(401, "Invalid or expired refresh token")

    user = await auth_service.get_user_by_id(db, record.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User not found")

    # Rotate tokens — revoke old, issue new pair
    await auth_service.revoke_refresh_token(db, body.refresh_token)
    access, expires_in = auth_service.create_access_token(user.id, user.role)
    refresh_new = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh_new, expires_in=expires_in)


@router.post("/logout", status_code=204)
async def logout(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    await auth_service.revoke_refresh_token(db, body.refresh_token)
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.has_seen_onboarding is not None:
        current_user.has_seen_onboarding = body.has_seen_onboarding
    await db.commit()
    await db.refresh(current_user)
    return current_user
