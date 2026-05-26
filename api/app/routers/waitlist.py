"""
Public waitlist endpoint — PRD-24 FR-3 to FR-7.
No auth required. Rate-limited 3/minute per IP.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import limiter
from app.models import WaitlistSignup
from app.schemas import WaitlistOut, WaitlistSubmit

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


@router.post("", response_model=WaitlistOut, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def join_waitlist(
    request: Request,
    body:    WaitlistSubmit,
    db:      AsyncSession = Depends(get_db),
) -> WaitlistOut:
    email_lower = body.email.strip().lower()

    # Check for existing row (case-insensitive)
    result = await db.execute(
        select(WaitlistSignup).where(WaitlistSignup.email.ilike(email_lower))
    )
    existing = result.scalars().first()

    if existing:
        # Enrich with any newly-provided non-null fields (upsert-style)
        if body.full_name   and not existing.full_name:   existing.full_name   = body.full_name
        if body.job_title   and not existing.job_title:   existing.job_title   = body.job_title
        if body.industry    and not existing.industry:    existing.industry    = body.industry
        if body.company     and not existing.company:     existing.company     = body.company
        if body.use_case    and not existing.use_case:    existing.use_case    = body.use_case
        if body.utm_source  and not existing.utm_source:  existing.utm_source  = body.utm_source
        if body.utm_medium  and not existing.utm_medium:  existing.utm_medium  = body.utm_medium
        if body.utm_campaign and not existing.utm_campaign: existing.utm_campaign = body.utm_campaign
        if body.marketing_consent:
            existing.marketing_consent = True
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to enrich existing waitlist row for %s", email_lower)
        return WaitlistOut(already_member=True)

    # New signup
    signup = WaitlistSignup(
        email             = body.email.strip(),
        full_name         = body.full_name,
        job_title         = body.job_title,
        industry          = body.industry,
        company           = body.company,
        use_case          = body.use_case,
        source            = body.source or "landing_hero_cta",
        referrer          = body.referrer,
        utm_source        = body.utm_source,
        utm_medium        = body.utm_medium,
        utm_campaign      = body.utm_campaign,
        marketing_consent = body.marketing_consent,
    )
    db.add(signup)
    try:
        await db.commit()
        await db.refresh(signup)
    except Exception:
        await db.rollback()
        log.exception("Failed to persist waitlist signup for %s", email_lower)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not save your signup — please try again shortly.",
        )

    return WaitlistOut(already_member=False)
