"""
Insights router — /api/boards/{board_id}/insights/*
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Insight, User
from app.schemas import InsightOut, InsightDismiss
from app.services import insight_service
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["insights"])


@router.get("/{board_id}/insights", response_model=list[InsightOut])
async def list_insights(
    board_id:          str,
    include_dismissed: bool = False,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    q = select(Insight).where(Insight.board_id == board_id)
    if not include_dismissed:
        q = q.where(Insight.is_dismissed.is_(False))
    q = q.order_by(Insight.generated_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/{board_id}/insights/generate", response_model=list[InsightOut], status_code=201)
async def generate_insights(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    """Trigger AI analysis of the board — creates and persists new insight cards."""
    await assert_board_access(db, board_id, user.id)
    created = await insight_service.generate_insights(db, board_id, user.id)
    await db.commit()
    # Refresh to get generated_at from DB
    for ins in created:
        await db.refresh(ins)
    return created


@router.patch("/{board_id}/insights/{insight_id}", response_model=InsightOut)
async def update_insight(
    board_id:   str,
    insight_id: str,
    body: InsightDismiss,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    result = await db.execute(
        select(Insight).where(
            Insight.id       == insight_id,
            Insight.board_id == board_id,
        )
    )
    ins = result.scalar_one_or_none()
    if not ins:
        raise HTTPException(404, "Insight not found")

    ins.is_dismissed = body.is_dismissed
    if body.is_dismissed:
        ins.dismissed_by = user.id
        ins.dismissed_at = datetime.now(timezone.utc)
    else:
        ins.dismissed_by = None
        ins.dismissed_at = None

    await db.commit()
    await db.refresh(ins)
    return ins


@router.delete("/{board_id}/insights/{insight_id}", status_code=204)
async def delete_insight(
    board_id:   str,
    insight_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    result = await db.execute(
        select(Insight).where(
            Insight.id       == insight_id,
            Insight.board_id == board_id,
        )
    )
    ins = result.scalar_one_or_none()
    if not ins:
        raise HTTPException(404, "Insight not found")
    await db.delete(ins)
    await db.commit()
