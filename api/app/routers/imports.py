"""
Imports router — /api/boards/{board_id}/import/*

POST   /api/boards/{id}/import                     → start extraction (synchronous)
GET    /api/boards/{id}/import/{job_id}            → poll status
POST   /api/boards/{id}/import/{job_id}/accept     → commit extraction result
DELETE /api/boards/{id}/import/{job_id}            → discard job
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import ImportAcceptRequest, ImportAcceptResponse, ImportJobOut, ImportStartRequest
from app.services import import_service
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["imports"])


@router.post("/{board_id}/import", response_model=ImportJobOut, status_code=200)
async def start_import(
    board_id: str,
    body:     ImportStartRequest,
    user:     User = Depends(get_current_user),
    db:       AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    job = await import_service.start_import(db, board_id, user.id, body.upload_id)
    await db.commit()
    return ImportJobOut(
        job_id=str(job.id),
        status=job.status,
        result=job.result,
        error=job.error,
    )


@router.get("/{board_id}/import/{job_id}", response_model=ImportJobOut)
async def get_import_job(
    board_id: str,
    job_id:   str,
    user:     User = Depends(get_current_user),
    db:       AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    job = await import_service.get_import_job(db, board_id, job_id)
    return ImportJobOut(
        job_id=str(job.id),
        status=job.status,
        result=job.result,
        error=job.error,
    )


@router.post("/{board_id}/import/{job_id}/accept", response_model=ImportAcceptResponse)
async def accept_import(
    board_id: str,
    job_id:   str,
    body:     ImportAcceptRequest,
    user:     User = Depends(get_current_user),
    db:       AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    result = await import_service.accept_import(db, board_id, job_id, user.id, body.edits)
    await db.commit()
    return ImportAcceptResponse(**result)


@router.delete("/{board_id}/import/{job_id}", status_code=204)
async def discard_import(
    board_id: str,
    job_id:   str,
    user:     User = Depends(get_current_user),
    db:       AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    await import_service.discard_import(db, board_id, job_id, user.id)
    await db.commit()
