"""Connectors router — PRD-18 (connector data model and CRUD API)."""
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import ConnectorCreate, ConnectorUpdate, ConnectorOut
from app.services.board_service import assert_board_access
from app.services import connector_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["connectors"])


@router.get("/{board_id}/connectors", response_model=list[ConnectorOut])
async def list_connectors(
    board_id: str,
    tier:     Annotated[Optional[str], Query()] = None,
    type:     Annotated[Optional[str], Query()] = None,
    user: User         = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    return await connector_service.list_connectors(db, board_id, tier=tier, type_=type)


@router.post("/{board_id}/connectors", response_model=ConnectorOut, status_code=201)
async def create_connector(
    board_id: str,
    body: ConnectorCreate,
    user: User         = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    board = await assert_board_access(db, board_id, user.id, require_role="editor")
    return await connector_service.create_connector(db, board, body, user_id=str(user.id))


@router.get("/{board_id}/connectors/{connector_id}", response_model=ConnectorOut)
async def get_connector(
    board_id:     str,
    connector_id: str,
    user: User         = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    return await connector_service.get_connector(db, board_id, connector_id)


@router.patch("/{board_id}/connectors/{connector_id}", response_model=ConnectorOut)
async def update_connector(
    board_id:     str,
    connector_id: str,
    body: ConnectorUpdate,
    user: User         = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    return await connector_service.update_connector(
        db, board_id, connector_id, body, user_id=str(user.id)
    )


@router.delete("/{board_id}/connectors/{connector_id}", status_code=204)
async def delete_connector(
    board_id:     str,
    connector_id: str,
    user: User         = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    await connector_service.delete_connector(
        db, board_id, connector_id, user_id=str(user.id)
    )
