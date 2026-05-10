"""
Elements router — /api/boards/{board_id}/elements
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import ElementCreate, ElementOut, ElementUpdate
from app.services.board_service import assert_board_access
from app.services.element_service import (
    list_elements, create_element, get_element, update_element, delete_element,
)
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["elements"])


@router.get("/{board_id}/elements", response_model=list[ElementOut])
async def list_elements_route(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    return await list_elements(db, board_id)


@router.post("/{board_id}/elements", response_model=ElementOut, status_code=201)
async def create_element_route(
    board_id: str,
    body: ElementCreate,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    return await create_element(db, board_id, body, user_id=str(user.id))


@router.get("/{board_id}/elements/{element_id}", response_model=ElementOut)
async def get_element_route(
    board_id:   str,
    element_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    return await get_element(db, board_id, element_id)


@router.patch("/{board_id}/elements/{element_id}", response_model=ElementOut)
async def update_element_route(
    board_id:   str,
    element_id: str,
    body: ElementUpdate,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    return await update_element(db, board_id, element_id, body, user_id=str(user.id))


@router.delete("/{board_id}/elements/{element_id}", status_code=204)
async def delete_element_route(
    board_id:   str,
    element_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    await delete_element(db, board_id, element_id, user_id=str(user.id))
