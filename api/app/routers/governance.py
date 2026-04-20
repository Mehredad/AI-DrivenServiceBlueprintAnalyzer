"""
Governance router — /api/boards/{board_id}/governance/*
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import GovernanceDecision, User
from app.schemas import GovernanceCreate, GovernanceOut
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["governance"])


@router.get("/{board_id}/governance", response_model=list[GovernanceOut])
async def list_governance(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    result = await db.execute(
        select(GovernanceDecision)
        .where(GovernanceDecision.board_id == board_id)
        .order_by(GovernanceDecision.decided_at.desc())
    )
    return result.scalars().all()


@router.post("/{board_id}/governance", response_model=GovernanceOut, status_code=201)
async def create_governance_decision(
    board_id: str,
    body: GovernanceCreate,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    decision = GovernanceDecision(
        board_id=board_id,
        decided_by=user.id,
        **body.model_dump(exclude_none=True),
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return decision


@router.patch("/{board_id}/governance/{decision_id}", response_model=GovernanceOut)
async def update_governance_decision(
    board_id:    str,
    decision_id: str,
    body: GovernanceCreate,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    result = await db.execute(
        select(GovernanceDecision).where(
            GovernanceDecision.id       == decision_id,
            GovernanceDecision.board_id == board_id,
        )
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(404, "Governance decision not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(decision, field, value)

    await db.commit()
    await db.refresh(decision)
    return decision


@router.delete("/{board_id}/governance/{decision_id}", status_code=204)
async def delete_governance_decision(
    board_id:    str,
    decision_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="admin")
    result = await db.execute(
        select(GovernanceDecision).where(
            GovernanceDecision.id       == decision_id,
            GovernanceDecision.board_id == board_id,
        )
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(404, "Governance decision not found")
    await db.delete(decision)
    await db.commit()
