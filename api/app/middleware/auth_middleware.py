"""
JWT auth dependency.
Usage: current_user: User = Depends(get_current_user)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.services.auth_service import decode_access_token, get_user_by_id

_bearer = HTTPBearer(auto_error=True)

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db:    AsyncSession                  = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(creds.credentials)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise _401
    except JWTError:
        raise _401

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise _401
    return user
