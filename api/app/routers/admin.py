"""
Admin-only waitlist management — PRD-24 FR-8 to FR-13.
All endpoints require is_admin=True.
"""
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_admin_user
from app.models import User, WaitlistSignup
from app.schemas import AdminWaitlistOut, WaitlistStatusPatch

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/waitlist", response_model=list[AdminWaitlistOut])
async def list_waitlist(
    limit:  int             = Query(50, ge=1, le=200),
    offset: int             = Query(0, ge=0),
    status: Optional[str]  = Query(None),
    sort:   str             = Query("created_at"),
    q:      Optional[str]  = Query(None, description="Search across name/email/company"),
    _admin: User            = Depends(get_admin_user),
    db:     AsyncSession    = Depends(get_db),
) -> list[WaitlistSignup]:
    allowed_sorts = {"created_at", "full_name", "industry", "status"}
    if sort not in allowed_sorts:
        raise HTTPException(status_code=400, detail=f"sort must be one of {allowed_sorts}")

    stmt = select(WaitlistSignup)

    if status:
        stmt = stmt.where(WaitlistSignup.status == status)

    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            or_(
                WaitlistSignup.email.ilike(term),
                WaitlistSignup.full_name.ilike(term),
                WaitlistSignup.company.ilike(term),
            )
        )

    sort_col = getattr(WaitlistSignup, sort)
    stmt = stmt.order_by(sort_col.desc() if sort == "created_at" else sort_col.asc())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/waitlist/export")
async def export_waitlist(
    status: Optional[str]  = Query(None),
    q:      Optional[str]  = Query(None),
    _admin: User           = Depends(get_admin_user),
    db:     AsyncSession   = Depends(get_db),
) -> StreamingResponse:
    stmt = select(WaitlistSignup).order_by(WaitlistSignup.created_at.desc())
    if status:
        stmt = stmt.where(WaitlistSignup.status == status)
    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            or_(
                WaitlistSignup.email.ilike(term),
                WaitlistSignup.full_name.ilike(term),
                WaitlistSignup.company.ilike(term),
            )
        )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "full_name", "email", "job_title", "industry", "company",
        "use_case", "status", "source", "created_at",
    ])
    for r in rows:
        writer.writerow([
            r.full_name or "", r.email, r.job_title or "", r.industry or "",
            r.company or "", r.use_case or "", r.status, r.source or "",
            r.created_at.isoformat() if r.created_at else "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waitlist.csv"'},
    )


@router.patch("/waitlist/{signup_id}/status", response_model=AdminWaitlistOut)
async def update_waitlist_status(
    signup_id: str,
    body:      WaitlistStatusPatch,
    _admin:    User         = Depends(get_admin_user),
    db:        AsyncSession = Depends(get_db),
) -> WaitlistSignup:
    result = await db.execute(select(WaitlistSignup).where(WaitlistSignup.id == signup_id))
    signup = result.scalars().first()
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
    signup.status = body.status
    await db.commit()
    await db.refresh(signup)
    return signup


@router.delete("/waitlist/{signup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_waitlist_signup(
    signup_id: str,
    _admin:    User         = Depends(get_admin_user),
    db:        AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(WaitlistSignup).where(WaitlistSignup.id == signup_id))
    signup = result.scalars().first()
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
    await db.delete(signup)
    await db.commit()
