"""
Auth router — /api/auth/*
"""
import logging
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

log = logging.getLogger(__name__)

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


@router.post("/google/debug")
async def google_debug(body: GoogleAuth):
    """Temporary: returns raw tokeninfo response so we can see what Google sends."""
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": body.credential},
            )
        return {"status": r.status_code, "body": r.json()}
    except Exception as exc:
        return {"error": str(exc)}


async def _verify_google_token(credential: str, client_id: str) -> dict:
    """Verify a Google ID token via Google's tokeninfo endpoint."""
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential},
            )
    except httpx.TimeoutException:
        log.error("Google tokeninfo request timed out")
        raise HTTPException(504, "Google authentication timed out — please try again")
    except httpx.HTTPError as exc:
        log.error("Google tokeninfo network error: %s", exc)
        raise HTTPException(502, "Could not reach Google's auth servers")

    if r.status_code != 200:
        log.warning("Google tokeninfo returned %d: %s", r.status_code, r.text[:200])
        raise HTTPException(401, "Invalid or expired Google credential")

    payload = r.json()
    log.info("Google tokeninfo payload keys: %s", list(payload.keys()))

    # aud check — Google tokeninfo returns the client_id as aud
    if payload.get("aud", "").strip() != client_id.strip():
        log.error(
            "Google aud mismatch: got %r expected %r",
            payload.get("aud"), client_id,
        )
        raise HTTPException(401, "Google token was not issued for this application")

    if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Invalid token issuer")

    # tokeninfo returns email_verified as the STRING "true"/"false", not a boolean
    if str(payload.get("email_verified", "false")).lower() != "true":
        raise HTTPException(401, "Google account email is not verified")

    return payload


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleAuth, db: AsyncSession = Depends(get_db)):
    """Exchange a Google ID token for Blueprint AI JWT tokens."""
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(501, "Google authentication is not configured on this server")

    try:
        payload = await _verify_google_token(body.credential, s.google_client_id)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Unexpected error verifying Google token: %s", exc)
        raise HTTPException(500, "Google sign-in verification failed unexpectedly")

    email = payload.get("email", "").lower().strip()
    if not email:
        raise HTTPException(401, "No email address in Google credential")

    full_name = (payload.get("name") or payload.get("given_name") or "").strip()

    try:
        user = await auth_service.get_user_by_email(db, email)
        if not user:
            log.info("Creating new user via Google Sign-In: %s", email)
            user = User(
                email=email,
                password_hash=auth_service.hash_password(secrets.token_hex(32)),
                full_name=full_name or None,
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
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("DB error during Google login for %s: %s", email, exc)
        await db.rollback()
        s = get_settings()
        detail = (
            f"Failed to create or retrieve your account ({type(exc).__name__}: {exc})"
            if s.environment == "development"
            else "Failed to create or retrieve your account"
        )
        raise HTTPException(500, detail)


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
