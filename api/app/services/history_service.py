"""History service — PRD-17a/17c snapshot-based change event log and restore."""
import logging
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models import Board, ChangeEvent, Element

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


# Fields from the element snapshot that are safe to apply back to the ORM model.
# Excludes server-managed fields (id, board_id, created_at, updated_at).
_SNAPSHOT_FIELDS = frozenset({
    "swimlane_id", "step_id", "type", "name", "notes", "owner", "status", "meta",
})


async def restore_element(
    db: AsyncSession,
    board_id: str,
    event: ChangeEvent,
    actor_user_id: Optional[str],
) -> tuple:
    """
    Restore an element to the state captured in a change event.

    - delete events: re-create the element using before_snapshot (same ID).
    - create/update/restore events: overwrite the current element using after_snapshot.

    Returns (element, warnings) where warnings is a list of string codes.
    """
    is_delete = event.operation == "delete"
    snap: Optional[dict[str, Any]] = event.before_snapshot if is_delete else event.after_snapshot

    if not snap:
        raise HTTPException(422, "No snapshot available for this event — cannot restore")

    entity_id = event.entity_id
    warnings: list[str] = []

    # AC-c3: check whether the swimlane the element belonged to still exists.
    swimlane_id = snap.get("swimlane_id")
    if swimlane_id:
        board_res = await db.execute(select(Board).where(Board.id == board_id))
        board = board_res.scalar_one_or_none()
        if board:
            sl_ids = {
                str(s["id"])
                for s in (board.state or {}).get("swimlanes", [])
                if "id" in s
            }
            if swimlane_id not in sl_ids:
                warnings.append("swimlane_not_found")
                snap = {**snap, "swimlane_id": None}

    field_vals = {k: snap.get(k) for k in _SNAPSHOT_FIELDS if k in snap}

    if is_delete:
        existing_res = await db.execute(
            select(Element).where(Element.id == entity_id, Element.board_id == board_id)
        )
        el = existing_res.scalar_one_or_none()
        if el:
            for k, v in field_vals.items():
                setattr(el, k, v)
        else:
            el = Element(
                id=entity_id,
                board_id=board_id,
                created_by_actor=snap.get("created_by_actor", "user"),
                **field_vals,
            )
            db.add(el)
    else:
        existing_res = await db.execute(
            select(Element).where(Element.id == entity_id, Element.board_id == board_id)
        )
        el = existing_res.scalar_one_or_none()
        if not el:
            raise HTTPException(
                404,
                "Element not found — it may have been deleted. "
                "To bring it back, restore the delete event instead.",
            )
        for k, v in field_vals.items():
            setattr(el, k, v)

    el.updated_by_user_id = actor_user_id
    el.updated_by_actor = "restore"

    await db.commit()
    await db.refresh(el)

    try:
        after_snap = _element_snapshot(el)
        await record_change_event(
            db, board_id, actor_user_id, "restore",
            "element", entity_id, "restore", None, after_snap,
        )
        await db.commit()
    except Exception as exc:
        log.warning("history restore event failed for element %s: %s", entity_id, exc)

    return el, warnings
