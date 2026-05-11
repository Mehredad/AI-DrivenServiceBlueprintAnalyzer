"""History router — /api/boards/{board_id}/history (PRD-17a/17c)"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, ChangeEvent
from app.schemas import ChangeEventOut, ElementOut
from app.services.board_service import assert_board_access
from app.services.history_service import list_history, get_change_event, restore_element
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["history"])


@router.get("/{board_id}/history", response_model=list[ChangeEventOut])
async def get_board_history(
    board_id: str,
    limit:  Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)]         = 0,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    events = await list_history(db, board_id, limit=limit, offset=offset)

    user_ids = {str(e.actor_user_id) for e in events if e.actor_user_id}
    names: dict[str, str] = {}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in result.scalars():
            names[str(u.id)] = u.full_name or u.email

    out = []
    for e in events:
        ev = ChangeEventOut.model_validate(e)
        ev.actor_name = names.get(str(e.actor_user_id)) if e.actor_user_id else None
        out.append(ev)
    return out


@router.get("/{board_id}/history/{event_id}", response_model=ChangeEventOut)
async def get_history_event(
    board_id: str,
    event_id: str,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    ev = await get_change_event(db, board_id, event_id)

    actor_name = None
    if ev.actor_user_id:
        result = await db.execute(select(User).where(User.id == ev.actor_user_id))
        u = result.scalar_one_or_none()
        if u:
            actor_name = u.full_name or u.email

    out = ChangeEventOut.model_validate(ev)
    out.actor_name = actor_name
    return out


@router.post("/{board_id}/history/{event_id}/restore")
async def restore_history_event(
    board_id: str,
    event_id: str,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    ev = await get_change_event(db, board_id, event_id)

    if ev.entity_type != "element":
        raise HTTPException(422, "Restore is currently only supported for element events")

    el, warnings = await restore_element(db, board_id, ev, actor_user_id=str(user.id))
    result: dict = {"restored": ElementOut.model_validate(el).model_dump(mode="json")}
    if warnings:
        result["warnings"] = warnings
    return result
