"""
Auth router — /api/auth/*
"""
import secrets
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserLogin, TokenRefresh, TokenResponse, UserOut, UserPatch, GoogleAuth
from app.services import auth_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
async def auth_config():
    """Return public auth configuration (client IDs safe to expose)."""
    s = get_settings()
    return {"google_client_id": s.google_client_id or None}


async def _verify_google_token(credential: str, client_id: str) -> dict:
    """Verify a Google ID token using Google's JWKS endpoint."""
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get("https://www.googleapis.com/oauth2/v3/certs")
        r.raise_for_status()
        jwks = r.json()

    try:
        payload = jwt.decode(
            credential,
            jwks,
            algorithms=["RS256"],
            audience=client_id,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise HTTPException(401, f"Invalid Google credential: {exc}")

    if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Invalid token issuer")
    if payload.get("exp", 0) < time.time():
        raise HTTPException(401, "Token expired")
    return payload


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleAuth, db: AsyncSession = Depends(get_db)):
    """Exchange a Google ID token for Blueprint AI JWT tokens."""
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(501, "Google authentication is not configured on this server")

    payload = await _verify_google_token(body.credential, s.google_client_id)

    email = payload.get("email", "").lower().strip()
    if not email:
        raise HTTPException(401, "No email address in Google credential")

    full_name = payload.get("name", "") or payload.get("given_name", "")

    user = await auth_service.get_user_by_email(db, email)
    if not user:
        user = User(
            email=email,
            password_hash=auth_service.hash_password(secrets.token_hex(32)),
            full_name=full_name,
            role="designer",
        )
        db.add(user)
        await db.flush()
    elif not user.is_active:
        raise HTTPException(403, "Account is disabled")

    user.last_login = datetime.now(timezone.utc)
    access, expires_in = auth_service.create_access_token(user.id, user.role)
    refresh = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


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
