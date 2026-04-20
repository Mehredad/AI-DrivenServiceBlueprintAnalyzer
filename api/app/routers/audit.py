"""
Audit router — /api/boards/{board_id}/audit
Read-only. Governance role required to access.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogOut
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["audit"])


@router.get("/{board_id}/audit", response_model=list[AuditLogOut])
async def get_audit_log(
    board_id: str,
    limit:    int = 100,
    offset:   int = 0,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    # Governance role check: only 'governance' or 'admin' collaborators + owner
    await assert_board_access(db, board_id, user.id)

    # Extra role-based gate: only governance officers and designers see audit log
    # (in production you'd store role per-board, here we use the user's global role)
    if user.role not in {"governance", "designer"}:
        raise HTTPException(403, "Audit log requires governance or designer role")

    if not 1 <= limit <= 500:
        raise HTTPException(400, "limit must be 1–500")

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.board_id == board_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
