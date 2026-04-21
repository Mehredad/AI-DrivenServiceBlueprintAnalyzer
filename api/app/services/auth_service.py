"""
Auth service — password hashing, JWT creation/validation, refresh token management.
Uses bcrypt directly (not passlib) for Vercel runtime compatibility.
"""
import hashlib
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, RefreshToken

settings = get_settings()


# ── Passwords ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    # Truncate to 72 bytes — bcrypt hard limit
    return bcrypt.hashpw(plain[:72].encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain[:72].encode(), hashed.encode())


# ── Access tokens (JWT, 15 min) ────────────────────────────────────────────────

def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    """Returns (token_string, expires_in_seconds)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "role": role, "exp": expire, "type": "access"}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, settings.access_token_expire_minutes * 60


def decode_access_token(token: str) -> dict:
    """Raises JWTError if token is invalid, expired, or wrong type."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


# ── Refresh tokens (opaque, stored as SHA-256 hash in DB) ─────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(db: AsyncSession, user_id: str) -> str:
    raw = secrets.token_urlsafe(64)
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(user_id=user_id, token_hash=_hash_token(raw), expires_at=expires))
    await db.flush()
    return raw


async def validate_refresh_token(db: AsyncSession, raw: str) -> Optional[RefreshToken]:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == _hash_token(raw),
            RefreshToken.expires_at  > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, raw: str) -> None:
    await db.execute(delete(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw)))


# ── User helpers ───────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
