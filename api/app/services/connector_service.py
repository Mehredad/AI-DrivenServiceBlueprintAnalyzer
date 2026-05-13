"""Connector service — PRD-18 (data model, validation, CRUD, cascades)."""
import logging
from typing import Optional
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models import Board, Connector, Element
from app.schemas import ConnectorCreate, ConnectorUpdate
from app.services.history_service import record_change_event

log = logging.getLogger(__name__)

_VALID_TYPES = {"sequence", "data_flow", "trigger", "dependency", "feedback", "failure"}


def _derive_tier(
    source_step_id:    Optional[str],
    source_element_id: Optional[str],
    target_step_id:    Optional[str],
    target_element_id: Optional[str],
) -> str:
    if source_step_id and target_step_id:
        return "step"
    if source_element_id and target_element_id:
        return "element"
    return "mixed"


async def _validate_endpoints(
    db:       AsyncSession,
    board:    Board,
    source_step_id:    Optional[str],
    source_element_id: Optional[str],
    target_step_id:    Optional[str],
    target_element_id: Optional[str],
) -> None:
    """Raise HTTPException if any endpoint constraint is violated."""
    src_set = (source_step_id is not None, source_element_id is not None)
    tgt_set = (target_step_id is not None, target_element_id is not None)

    if sum(src_set) != 1:
        raise HTTPException(400, "Exactly one of source_step_id or source_element_id must be set")
    if sum(tgt_set) != 1:
        raise HTTPException(400, "Exactly one of target_step_id or target_element_id must be set")

    # Self-loop check
    if source_step_id and source_step_id == target_step_id:
        raise HTTPException(400, "Source and target cannot be the same step")
    if source_element_id and source_element_id == target_element_id:
        raise HTTPException(400, "Source and target cannot be the same element")

    # Validate step IDs exist in boards.state.steps
    step_ids_to_check = {s for s in [source_step_id, target_step_id] if s}
    if step_ids_to_check:
        board_step_ids = {
            str(s["id"])
            for s in (board.state or {}).get("steps", [])
            if "id" in s
        }
        missing = step_ids_to_check - board_step_ids
        if missing:
            raise HTTPException(400, f"Step ID(s) not found on this board: {', '.join(missing)}")

    # Validate element IDs belong to this board
    el_ids_to_check = [e for e in [source_element_id, target_element_id] if e]
    for el_id in el_ids_to_check:
        result = await db.execute(
            select(Element).where(Element.id == el_id, Element.board_id == str(board.id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(400, f"Element {el_id} not found on this board")


async def list_connectors(
    db:       AsyncSession,
    board_id: str,
    tier:     Optional[str] = None,
    type_:    Optional[str] = None,
) -> list[Connector]:
    q = select(Connector).where(Connector.board_id == board_id)
    if tier:
        q = q.where(Connector.tier == tier)
    if type_:
        q = q.where(Connector.connector_type == type_)
    q = q.order_by(Connector.created_at)
    result = await db.execute(q)
    return result.scalars().all()


async def get_connector(
    db:           AsyncSession,
    board_id:     str,
    connector_id: str,
) -> Connector:
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id, Connector.board_id == board_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Connector not found")
    return c


async def create_connector(
    db:       AsyncSession,
    board:    Board,
    data:     ConnectorCreate,
    user_id:  Optional[str] = None,
) -> Connector:
    await _validate_endpoints(
        db, board,
        data.source_step_id, data.source_element_id,
        data.target_step_id, data.target_element_id,
    )
    tier = _derive_tier(
        data.source_step_id, data.source_element_id,
        data.target_step_id, data.target_element_id,
    )
    c = Connector(
        board_id           = str(board.id),
        source_step_id     = data.source_step_id,
        source_element_id  = data.source_element_id,
        target_step_id     = data.target_step_id,
        target_element_id  = data.target_element_id,
        tier               = tier,
        connector_type     = data.connector_type,
        label              = data.label,
        notes              = data.notes,
        waypoints          = data.waypoints or [],
        created_by_user_id = user_id,
        created_by_actor   = data.actor,
        updated_by_user_id = user_id,
        updated_by_actor   = data.actor,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)

    try:
        await record_change_event(
            db, str(board.id), user_id, data.actor,
            "connector", str(c.id), "create", None,
            {"id": str(c.id), "type": c.connector_type, "tier": c.tier},
            commit_message=f"Created {c.connector_type} connector",
        )
        await db.commit()
    except Exception as exc:
        log.warning("history event failed (connector create) %s: %s", c.id, exc)

    await _broadcast(str(board.id), "create", str(c.id))
    return c


async def update_connector(
    db:           AsyncSession,
    board_id:     str,
    connector_id: str,
    data:         ConnectorUpdate,
    user_id:      Optional[str] = None,
) -> Connector:
    c = await get_connector(db, board_id, connector_id)

    if data.connector_type is not None:
        c.connector_type = data.connector_type
    if data.label is not None:
        c.label = data.label
    if data.notes is not None:
        c.notes = data.notes
    if data.waypoints is not None:
        c.waypoints = data.waypoints
    c.updated_by_user_id = user_id
    c.updated_by_actor   = "user"

    await db.commit()
    await db.refresh(c)

    try:
        await record_change_event(
            db, board_id, user_id, "user",
            "connector", connector_id, "update", None,
            {"id": str(c.id), "type": c.connector_type},
            commit_message=f"Updated {c.connector_type} connector",
        )
        await db.commit()
    except Exception as exc:
        log.warning("history event failed (connector update) %s: %s", connector_id, exc)

    await _broadcast(board_id, "update", connector_id)
    return c


async def delete_connector(
    db:           AsyncSession,
    board_id:     str,
    connector_id: str,
    user_id:      Optional[str] = None,
) -> None:
    c = await get_connector(db, board_id, connector_id)
    await db.delete(c)
    await db.commit()

    try:
        await record_change_event(
            db, board_id, user_id, "user",
            "connector", connector_id, "delete",
            {"id": connector_id}, None,
            commit_message="Deleted connector",
        )
        await db.commit()
    except Exception as exc:
        log.warning("history event failed (connector delete) %s: %s", connector_id, exc)

    await _broadcast(board_id, "delete", connector_id)


async def delete_connectors_for_step(
    db:           AsyncSession,
    board_id:     str,
    step_id:      str,
    actor_user_id: Optional[str] = None,
) -> int:
    """Delete all connectors referencing step_id on this board. Returns deleted count."""
    result = await db.execute(
        select(Connector).where(
            Connector.board_id == board_id,
            (Connector.source_step_id == step_id) | (Connector.target_step_id == step_id),
        )
    )
    connectors = result.scalars().all()
    for c in connectors:
        await db.delete(c)
        try:
            await record_change_event(
                db, board_id, actor_user_id, "system",
                "connector", str(c.id), "delete",
                {"id": str(c.id), "reason": f"step {step_id} deleted"}, None,
            )
        except Exception as exc:
            log.warning("history event failed (step cascade connector) %s: %s", c.id, exc)
    if connectors:
        await db.commit()
    return len(connectors)


async def delete_connectors_for_element(
    db:           AsyncSession,
    board_id:     str,
    element_id:   str,
    actor_user_id: Optional[str] = None,
) -> int:
    """
    Explicitly delete connectors referencing element_id and log history events.
    Explicit deletion ensures correctness in SQLite (no FK cascade) and on PostgreSQL
    the FK ON DELETE CASCADE is a harmless no-op afterwards.
    """
    result = await db.execute(
        select(Connector).where(
            Connector.board_id == board_id,
            (Connector.source_element_id == element_id) | (Connector.target_element_id == element_id),
        )
    )
    connectors = result.scalars().all()
    for c in connectors:
        await db.delete(c)
        try:
            await record_change_event(
                db, board_id, actor_user_id, "system",
                "connector", str(c.id), "delete",
                {"id": str(c.id), "reason": f"element {element_id} deleted"}, None,
            )
        except Exception as exc:
            log.warning("history event failed (element cascade connector) %s: %s", c.id, exc)
    if connectors:
        await db.commit()
    return len(connectors)


async def _broadcast(board_id: str, operation: str, connector_id: str) -> None:
    """Best-effort Supabase Realtime broadcast. Never raises."""
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_key:
            return
        if "sqlite" in settings.database_url:
            return  # skip in test/SQLite environments
        import httpx
        payload = {
            "messages": [{
                "topic":   f"realtime:board:{board_id}",
                "event":   "broadcast",
                "payload": {
                    "type":  "broadcast",
                    "event": "connector_changed",
                    "payload": {
                        "operation":    operation,
                        "connector_id": connector_id,
                    },
                },
            }]
        }
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(
                f"{settings.supabase_url}/realtime/v1/api/broadcast",
                json=payload,
                headers={"Authorization": f"Bearer {settings.supabase_service_key}"},
            )
    except Exception as exc:
        log.debug("realtime broadcast skipped: %s", exc)
