"""
Boards router — /api/boards/*
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import (
    BoardCreate, BoardPatch, BoardOut, BoardSummary, CollaboratorAdd, CollaboratorOut,
)
from app.services import board_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["boards"])


@router.get("", response_model=list[BoardSummary])
async def list_boards(
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    return await board_service.list_boards(db, user.id)


@router.post("", response_model=BoardOut, status_code=201)
async def create_board(
    body: BoardCreate,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    board = await board_service.create_board(db, user.id, body)
    await db.commit()
    await db.refresh(board)
    return board


@router.get("/{board_id}", response_model=BoardOut)
async def get_board(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    return await board_service.get_board(db, board_id, user.id)


@router.patch("/{board_id}", response_model=BoardOut)
async def patch_board(
    board_id: str,
    body:    BoardPatch,
    request: Request,
    user:    User = Depends(get_current_user),
    db:      AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    board = await board_service.patch_board(db, board_id, user.id, body, ip=ip, ua=ua)
    await db.commit()
    await db.refresh(board)
    return board


@router.delete("/{board_id}", status_code=204)
async def archive_board(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await board_service.archive_board(db, board_id, user.id)
    await db.commit()


@router.get("/{board_id}/collaborators", response_model=list[CollaboratorOut])
async def list_collaborators(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    return await board_service.list_collaborators(db, board_id, user.id)


@router.post("/{board_id}/collaborators", status_code=201)
async def add_collaborator(
    board_id: str,
    body: CollaboratorAdd,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    collab = await board_service.add_collaborator(db, board_id, user.id, body.email, body.role)
    await db.commit()
    return {"board_id": collab.board_id, "user_id": collab.user_id, "role": collab.role}


@router.delete("/{board_id}/collaborators/{target_user_id}", status_code=204)
async def remove_collaborator(
    board_id:       str,
    target_user_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await board_service.remove_collaborator(db, board_id, user.id, target_user_id)
    await db.commit()
