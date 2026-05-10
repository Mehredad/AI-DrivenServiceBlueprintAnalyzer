"""History service — PRD-17a snapshot-based change event log."""
import logging
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models import ChangeEvent

log = logging.getLogger(__name__)


def _element_snapshot(el) -> dict[str, Any]:
    """Serialize an Element ORM object to a JSON-safe dict for snapshotting."""
    from app.schemas import ElementOut
    return ElementOut.model_validate(el).model_dump(mode="json")


async def record_change_event(
    db: AsyncSession,
    board_id: str,
    actor_user_id: Optional[str],
    actor_type: str,
    entity_type: str,
    entity_id: str,
    operation: str,
    before_snapshot: Optional[dict[str, Any]],
    after_snapshot: Optional[dict[str, Any]],
) -> None:
    ev = ChangeEvent(
        board_id=board_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    db.add(ev)


async def list_history(
    db: AsyncSession,
    board_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[ChangeEvent]:
    result = await db.execute(
        select(ChangeEvent)
        .where(ChangeEvent.board_id == board_id)
        .order_by(ChangeEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def get_change_event(
    db: AsyncSession,
    board_id: str,
    event_id: str,
) -> ChangeEvent:
    result = await db.execute(
        select(ChangeEvent).where(
            ChangeEvent.id == event_id,
            ChangeEvent.board_id == board_id,
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(404, "Change event not found")
    return ev
