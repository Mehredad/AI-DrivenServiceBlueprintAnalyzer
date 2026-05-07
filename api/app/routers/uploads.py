"""
Uploads router — /api/boards/{board_id}/uploads/*

POST   /api/boards/{id}/uploads/sign           → signed PUT URL for direct browser upload
GET    /api/boards/{id}/uploads/{upload_id}/url → short-lived signed download URL
DELETE /api/boards/{id}/uploads/{upload_id}     → remove from storage + DB
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UploadSignRequest, UploadSignResponse, UploadUrlResponse
from app.services import upload_service
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["uploads"])


@router.post("/{board_id}/uploads/sign", response_model=UploadSignResponse, status_code=201)
async def sign_upload(
    board_id: str,
    body: UploadSignRequest,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    return await upload_service.sign_upload(
        db, board_id, user.id, body.filename, body.content_type, body.size
    )


@router.get("/{board_id}/uploads/{upload_id}/url", response_model=UploadUrlResponse)
async def get_upload_url(
    board_id:  str,
    upload_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    return await upload_service.get_download_url(db, board_id, upload_id)


@router.delete("/{board_id}/uploads/{upload_id}", status_code=204)
async def delete_upload(
    board_id:  str,
    upload_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    await upload_service.delete_upload(db, board_id, upload_id, user.id)
