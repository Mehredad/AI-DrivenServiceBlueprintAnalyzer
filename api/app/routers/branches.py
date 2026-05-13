"""Branches router — PRD-17d (branch switcher UI and data model)"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Board, Branch, Element, User
from app.schemas import BranchCreate, BranchOut
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["branches"])


@router.get("/{board_id}/branches", response_model=list[BranchOut])
async def list_branches(
    board_id: str,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    result = await db.execute(
        select(Branch).where(Branch.board_id == board_id).order_by(Branch.created_at)
    )
    branches = result.scalars().all()
    if not branches:
        main = Branch(
            board_id=board_id,
            name="main",
            is_default=True,
            created_by_user_id=str(user.id),
        )
        db.add(main)
        await db.commit()
        await db.refresh(main)
        branches = [main]
    return branches


@router.post("/{board_id}/branches", response_model=BranchOut, status_code=201)
async def create_branch(
    board_id: str,
    body: BranchCreate,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")

    # Snapshot current board structure (swimlanes + steps from board.state)
    board_res = await db.execute(select(Board).where(Board.id == board_id))
    board = board_res.scalar_one_or_none()
    state_snapshot: dict[str, Any] = {}
    if board and board.state:
        state_snapshot = {
            "swimlanes": board.state.get("swimlanes", []),
            "steps":     board.state.get("steps",     []),
        }

    branch = Branch(
        board_id=board_id,
        name=body.name,
        is_default=False,
        state_snapshot=state_snapshot,
        created_by_user_id=str(user.id),
    )
    db.add(branch)
    try:
        await db.flush()  # get branch.id before copying elements
    except Exception:
        await db.rollback()
        raise HTTPException(409, f"A branch named '{body.name}' already exists on this board")

    # Copy all main-branch elements (branch_id IS NULL) to the new branch
    el_result = await db.execute(
        select(Element).where(
            Element.board_id == board_id,
            Element.branch_id.is_(None),
        )
    )
    for src in el_result.scalars().all():
        copy = Element(
            board_id=board_id,
            branch_id=str(branch.id),
            swimlane_id=src.swimlane_id,
            step_id=src.step_id,
            type=src.type,
            name=src.name,
            notes=src.notes,
            owner=src.owner,
            status=src.status,
            meta=src.meta or {},
            created_by_user_id=str(user.id),
            created_by_actor="system",
            updated_by_user_id=str(user.id),
            updated_by_actor="system",
        )
        db.add(copy)

    await db.commit()
    await db.refresh(branch)
    return branch


@router.patch("/{board_id}/branches/{branch_id}/state", status_code=200)
async def patch_branch_state(
    board_id:  str,
    branch_id: str,
    request:   Request,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id, Branch.board_id == board_id)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(404, "Branch not found")
    if branch.is_default:
        raise HTTPException(422, "Use PATCH /api/boards/{id} to update the main branch state")

    patch: dict[str, Any] = await request.json()
    current = dict(branch.state_snapshot or {})
    current.update(patch)
    branch.state_snapshot = current
    await db.commit()
    return {"state_snapshot": branch.state_snapshot}


@router.delete("/{board_id}/branches/{branch_id}", status_code=204)
async def delete_branch(
    board_id:  str,
    branch_id: str,
    user: User          = Depends(get_current_user),
    db:   AsyncSession  = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id, Branch.board_id == board_id)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(404, "Branch not found")
    if branch.is_default:
        raise HTTPException(422, "Cannot delete the default branch")
    await db.delete(branch)
    await db.commit()
