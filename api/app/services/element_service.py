"""
Element service — CRUD for the unified element model.
For ai_capability elements, also syncs to the capabilities table (best-effort).
"""
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models import Element, Capability
from app.schemas import ElementCreate, ElementUpdate

log = logging.getLogger(__name__)


async def list_elements(db: AsyncSession, board_id: str) -> list[Element]:
    result = await db.execute(
        select(Element)
        .where(Element.board_id == board_id)
        .order_by(Element.created_at)
    )
    return result.scalars().all()


async def get_element(db: AsyncSession, board_id: str, element_id: str) -> Element:
    result = await db.execute(
        select(Element).where(Element.id == element_id, Element.board_id == board_id)
    )
    el = result.scalar_one_or_none()
    if not el:
        raise HTTPException(404, "Element not found")
    return el


async def create_element(db: AsyncSession, board_id: str, data: ElementCreate) -> Element:
    el = Element(board_id=board_id, **data.model_dump(exclude_none=True))
    db.add(el)
    await db.flush()

    if el.type == "ai_capability":
        await _sync_capability_create(db, board_id, el)

    await db.commit()
    await db.refresh(el)
    return el


async def update_element(
    db: AsyncSession, board_id: str, element_id: str, data: ElementUpdate
) -> Element:
    el = await get_element(db, board_id, element_id)
    old_type = el.type

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(el, k, v)

    new_type = el.type
    if old_type == "ai_capability" and new_type != "ai_capability":
        await _sync_capability_delete(db, board_id, element_id)
    elif new_type == "ai_capability":
        await _sync_capability_upsert(db, board_id, el)

    await db.commit()
    await db.refresh(el)
    return el


async def delete_element(db: AsyncSession, board_id: str, element_id: str) -> None:
    el = await get_element(db, board_id, element_id)
    if el.type == "ai_capability":
        await _sync_capability_delete(db, board_id, element_id)
    await db.delete(el)
    await db.commit()


# ── Capability sync helpers (best-effort) ─────────────────────────────────────

async def _sync_capability_create(db: AsyncSession, board_id: str, el: Element) -> None:
    try:
        meta = el.meta or {}
        cap = Capability(
            board_id=board_id,
            cap_id=meta.get("cap_id") or f"CAP-{str(el.id)[:6].upper()}",
            name=el.name,
            type=meta.get("ai_type"),
            risk_level=meta.get("risk_level"),
            frontstage=bool(meta.get("frontstage", True)),
            xai_strategy=meta.get("xai_strategy"),
            autonomy=meta.get("autonomy"),
            owner=el.owner,
            status=el.status or "draft",
            notes=el.notes,
            meta={"element_id": str(el.id)},
        )
        db.add(cap)
        await db.flush()
    except Exception as exc:
        log.warning("capability sync (create) failed for element %s: %s", el.id, exc)


async def _sync_capability_upsert(db: AsyncSession, board_id: str, el: Element) -> None:
    try:
        meta = el.meta or {}
        result = await db.execute(
            select(Capability).where(
                Capability.board_id == board_id,
                Capability.meta["element_id"].astext == str(el.id),
            )
        )
        cap = result.scalar_one_or_none()
        if cap:
            cap.name = el.name
            cap.type = meta.get("ai_type")
            cap.risk_level = meta.get("risk_level")
            cap.frontstage = bool(meta.get("frontstage", True))
            cap.xai_strategy = meta.get("xai_strategy")
            cap.autonomy = meta.get("autonomy")
            cap.owner = el.owner
            cap.status = el.status or "draft"
            cap.notes = el.notes
        else:
            await _sync_capability_create(db, board_id, el)
    except Exception as exc:
        log.warning("capability sync (upsert) failed for element %s: %s", el.id, exc)


async def _sync_capability_delete(
    db: AsyncSession, board_id: str, element_id: str
) -> None:
    try:
        result = await db.execute(
            select(Capability).where(
                Capability.board_id == board_id,
                Capability.meta["element_id"].astext == element_id,
            )
        )
        cap = result.scalar_one_or_none()
        if cap:
            await db.delete(cap)
    except Exception as exc:
        log.warning("capability sync (delete) failed for element %s: %s", element_id, exc)
