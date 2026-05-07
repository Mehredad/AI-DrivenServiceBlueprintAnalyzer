"""
Upload service — Supabase Storage integration for file attachments.

Uses the Supabase Storage REST API directly via httpx (no supabase-py dep needed).
Flow:
  1. sign_upload   → create DB row + return a signed PUT URL for the browser
  2. get_download_url → generate a short-lived signed download URL
  3. download_bytes   → fetch raw bytes (called by agent_service before Anthropic)
  4. delete_upload    → remove from storage + DB
"""
import uuid
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Upload
from app.services.board_service import assert_board_access

settings = get_settings()

BUCKET        = "board-uploads"
DAILY_LIMIT   = 50
MAX_SIZE      = 10 * 1024 * 1024   # 10 MB
ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def _svc_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type":  "application/json",
    }


def _require_storage() -> None:
    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(503, "File storage is not configured on this deployment.")


async def count_user_uploads_today(db: AsyncSession, user_id: str) -> int:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(Upload.id)).where(
            Upload.user_id == user_id,
            Upload.created_at >= today,
        )
    )
    return result.scalar() or 0


async def sign_upload(
    db:           AsyncSession,
    board_id:     str,
    user_id:      str,
    filename:     str,
    content_type: str,
    size:         int,
) -> dict:
    _require_storage()

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(422, "Unsupported file type. PDF or images only.")
    if size > MAX_SIZE:
        raise HTTPException(422, "File too large. Max 10 MB.")

    today_count = await count_user_uploads_today(db, user_id)
    if today_count >= DAILY_LIMIT:
        raise HTTPException(429, "Daily upload limit reached.")

    upload_id = str(uuid.uuid4())
    safe_name = filename.replace("/", "_").replace("..", "_")[:200]
    storage_path = f"boards/{board_id}/uploads/{upload_id}-{safe_name}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.supabase_url}/storage/v1/object/upload/sign/{BUCKET}/{storage_path}",
            headers=_svc_headers(),
            json={"expiresIn": 3600},
        )
        if resp.status_code not in (200, 201):
            raise HTTPException(502, f"Storage signing failed: {resp.text[:200]}")
        data = resp.json()

    # Supabase returns a relative path like /object/upload/sign/...?token=...
    # We must make it absolute so the browser can PUT directly to Supabase.
    upload_url: str = data.get("url") or data.get("signedUrl", "")
    if upload_url and not upload_url.startswith("http"):
        upload_url = f"{settings.supabase_url}/storage/v1{upload_url}"

    upload = Upload(
        id=upload_id,
        board_id=board_id,
        user_id=user_id,
        filename=safe_name,
        content_type=content_type,
        size_bytes=size,
        storage_path=storage_path,
    )
    db.add(upload)
    await db.flush()

    return {"upload_id": upload_id, "upload_url": upload_url}


async def get_download_url(
    db:        AsyncSession,
    board_id:  str,
    upload_id: str,
) -> dict:
    _require_storage()

    result = await db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.board_id == board_id)
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(404, "Upload not found.")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.supabase_url}/storage/v1/object/sign/{BUCKET}/{upload.storage_path}",
            headers=_svc_headers(),
            json={"expiresIn": 300},
        )
        if resp.status_code not in (200, 201):
            raise HTTPException(502, f"Storage URL generation failed: {resp.text[:200]}")
        data = resp.json()

    signed = data.get("signedURL") or data.get("signedUrl", "")
    if not signed.startswith("http"):
        signed = settings.supabase_url + signed

    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
    return {"url": signed, "expires_at": expires_at}


async def download_bytes(storage_path: str) -> bytes:
    _require_storage()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{storage_path}",
            headers={"Authorization": f"Bearer {settings.supabase_service_key}"},
        )
        if resp.status_code != 200:
            raise HTTPException(502, "Failed to fetch attached file from storage.")
        return resp.content


async def delete_upload(
    db:        AsyncSession,
    board_id:  str,
    upload_id: str,
    user_id:   str,
) -> None:
    result = await db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.board_id == board_id)
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(404, "Upload not found.")

    if upload.user_id != user_id:
        board = await assert_board_access(db, board_id, user_id)
        if board.owner_id != user_id:
            raise HTTPException(403, "Cannot delete another user's upload.")

    if settings.supabase_url and settings.supabase_service_key:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.delete(
                f"{settings.supabase_url}/storage/v1/object/{BUCKET}",
                headers=_svc_headers(),
                json={"prefixes": [upload.storage_path]},
            )

    await db.delete(upload)
    await db.flush()
