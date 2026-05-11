"""History router — /api/boards/{board_id}/history + /commits (PRD-17a/17c/17e)"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Commit, User, ChangeEvent
from app.schemas import ChangeEventOut, CommitOut, ElementOut, GroupCommitRequest
from app.services.board_service import assert_board_access
from app.services.history_service import (
    list_history, get_change_event, restore_element,
    list_commits, group_events_into_commit,
)
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

    # Load commit messages for events that belong to a commit
    commit_ids = {str(e.commit_id) for e in events if e.commit_id}
    commit_msgs: dict[str, str] = {}
    if commit_ids:
        cr = await db.execute(select(Commit).where(Commit.id.in_(commit_ids)))
        for c in cr.scalars():
            commit_msgs[str(c.id)] = c.message

    out = []
    for e in events:
        ev = ChangeEventOut.model_validate(e)
        ev.actor_name     = names.get(str(e.actor_user_id)) if e.actor_user_id else None
        ev.commit_message = commit_msgs.get(str(e.commit_id)) if e.commit_id else None
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


@router.get("/{board_id}/commits", response_model=list[CommitOut])
async def list_board_commits(
    board_id: str,
    limit:  Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)]         = 0,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    rows = await list_commits(db, board_id, limit=limit, offset=offset)

    author_ids = {str(c.author_user_id) for c, _ in rows if c.author_user_id}
    names: dict[str, str] = {}
    if author_ids:
        ur = await db.execute(select(User).where(User.id.in_(author_ids)))
        for u in ur.scalars():
            names[str(u.id)] = u.full_name or u.email

    out = []
    for commit, event_count in rows:
        co = CommitOut.model_validate(commit)
        co.author_name = names.get(str(commit.author_user_id)) if commit.author_user_id else None
        co.event_count = event_count
        out.append(co)
    return out


@router.post("/{board_id}/commits", response_model=CommitOut, status_code=201)
async def create_group_commit(
    board_id: str,
    body: GroupCommitRequest,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    commit = await group_events_into_commit(
        db, board_id, body.event_ids, body.message, actor_user_id=str(user.id)
    )
    await db.commit()
    await db.refresh(commit)
    co = CommitOut.model_validate(commit)
    co.author_name = user.full_name or user.email
    co.event_count = len(body.event_ids)
    return co


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
