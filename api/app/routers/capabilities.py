"""
Capabilities router — /api/boards/{board_id}/capabilities
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Capability, User
from app.schemas import CapabilityCreate, CapabilityOut
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["capabilities"])


@router.get("/{board_id}/capabilities", response_model=list[CapabilityOut])
async def list_capabilities(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    result = await db.execute(
        select(Capability)
        .where(Capability.board_id == board_id)
        .order_by(Capability.created_at)
    )
    return result.scalars().all()


@router.post("/{board_id}/capabilities", response_model=CapabilityOut, status_code=201)
async def create_capability(
    board_id: str,
    body: CapabilityCreate,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")

    # Prevent duplicate cap_id within same board
    existing = await db.execute(
        select(Capability).where(
            Capability.board_id == board_id,
            Capability.cap_id   == body.cap_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Capability '{body.cap_id}' already exists on this board")

    cap = Capability(board_id=board_id, **body.model_dump(exclude_none=True))
    db.add(cap)
    await db.commit()
    await db.refresh(cap)
    return cap


@router.patch("/{board_id}/capabilities/{cap_id}", response_model=CapabilityOut)
async def update_capability(
    board_id: str,
    cap_id:   str,
    body: CapabilityCreate,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    result = await db.execute(
        select(Capability).where(
            Capability.id       == cap_id,
            Capability.board_id == board_id,
        )
    )
    cap = result.scalar_one_or_none()
    if not cap:
        raise HTTPException(404, "Capability not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cap, field, value)

    await db.commit()
    await db.refresh(cap)
    return cap


@router.delete("/{board_id}/capabilities/{cap_id}", status_code=204)
async def delete_capability(
    board_id: str,
    cap_id:   str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    result = await db.execute(
        select(Capability).where(
            Capability.id       == cap_id,
            Capability.board_id == board_id,
        )
    )
    cap = result.scalar_one_or_none()
    if not cap:
        raise HTTPException(404, "Capability not found")
    await db.delete(cap)
    await db.commit()
