"""
Board service — CRUD, collaborator management, optimistic-lock state merging, audit trail.
Every mutating operation writes to audit_logs.
"""
from typing import Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models import Board, BoardCollaborator, User, AuditLog
from app.schemas import BoardCreate, BoardPatch, CollaboratorOut


# ── Access control ────────────────────────────────────────────────────────────

async def assert_board_access(
    db: AsyncSession,
    board_id: str,
    user_id: str,
    require_role: Optional[str] = None,   # None=any, "editor", "admin"
) -> Board:
    result = await db.execute(
        select(Board)
        .options(selectinload(Board.collaborators))
        .where(Board.id == board_id, Board.is_archived.is_(False))
    )
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(404, "Board not found")

    if board.owner_id == user_id:
        return board  # owner has all rights

    collab = next((c for c in board.collaborators if c.user_id == user_id), None)
    if not collab:
        raise HTTPException(403, "You don't have access to this board")

    role_rank = {"viewer": 0, "editor": 1, "admin": 2}
    required  = role_rank.get(require_role or "viewer", 0)
    actual    = role_rank.get(collab.role, 0)
    if actual < required:
        raise HTTPException(403, f"'{require_role}' role required")

    return board


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_boards(db: AsyncSession, user_id: str) -> list[Board]:
    collab_ids = (
        select(BoardCollaborator.board_id)
        .where(BoardCollaborator.user_id == user_id)
        .scalar_subquery()
    )
    result = await db.execute(
        select(Board)
        .where(
            Board.is_archived.is_(False),
            or_(Board.owner_id == user_id, Board.id.in_(collab_ids)),
        )
        .order_by(Board.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_board(db: AsyncSession, user_id: str, data: BoardCreate) -> Board:
    board = Board(
        owner_id=user_id,
        title=data.title,
        domain=data.domain,
        state={"steps": [], "swimlanes": [], "cards": {}, "capabilities": []},
    )
    db.add(board)
    await db.flush()
    _audit(db, board.id, user_id, "board.create", "board", board.id)
    return board


async def get_board(db: AsyncSession, board_id: str, user_id: str) -> Board:
    return await assert_board_access(db, board_id, user_id)


async def patch_board(
    db: AsyncSession,
    board_id: str,
    user_id: str,
    data: BoardPatch,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
) -> tuple:
    """Returns (board, removed_step_ids) so callers can cascade-delete connectors."""
    board = await assert_board_access(db, board_id, user_id, require_role="editor")
    old_state = dict(board.state or {})

    removed_step_ids: set[str] = set()
    if data.title  is not None: board.title  = data.title
    if data.domain is not None: board.domain = data.domain
    if data.phase  is not None: board.phase  = data.phase
    if data.state  is not None:
        old_step_ids = {str(s["id"]) for s in old_state.get("steps", []) if "id" in s}
        board.state = {**board.state, **data.state}  # shallow merge
        new_step_ids = {str(s["id"]) for s in board.state.get("steps", []) if "id" in s}
        removed_step_ids = old_step_ids - new_step_ids

    board.version += 1
    _audit(db, board_id, user_id, "board.update", "board", board_id,
           diff={"before": old_state, "after": board.state}, ip=ip, ua=ua)
    return board, removed_step_ids


async def archive_board(db: AsyncSession, board_id: str, user_id: str) -> None:
    board = await assert_board_access(db, board_id, user_id, require_role="admin")
    board.is_archived = True
    _audit(db, board_id, user_id, "board.archive", "board", board_id)


# ── Collaborators ─────────────────────────────────────────────────────────────

async def list_collaborators(
    db: AsyncSession,
    board_id: str,
    user_id: str,
) -> list[CollaboratorOut]:
    await assert_board_access(db, board_id, user_id)
    result = await db.execute(
        select(BoardCollaborator, User)
        .join(User, BoardCollaborator.user_id == User.id)
        .where(BoardCollaborator.board_id == board_id)
    )
    return [
        CollaboratorOut(
            user_id=str(row.BoardCollaborator.user_id),
            email=row.User.email,
            full_name=row.User.full_name,
            role=row.BoardCollaborator.role,
            joined_at=row.BoardCollaborator.joined_at,
        )
        for row in result.all()
    ]


async def add_collaborator(
    db: AsyncSession,
    board_id: str,
    requester_id: str,
    target_email: str,
    role: str,
) -> BoardCollaborator:
    board = await assert_board_access(db, board_id, requester_id, require_role="admin")

    target_result = await db.execute(select(User).where(User.email == target_email.lower()))
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == board.owner_id:
        raise HTTPException(400, "User is already the board owner")

    existing = await db.execute(
        select(BoardCollaborator).where(
            BoardCollaborator.board_id == board_id,
            BoardCollaborator.user_id  == target.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "User is already a collaborator")

    collab = BoardCollaborator(board_id=board_id, user_id=target.id, role=role)
    db.add(collab)
    _audit(db, board_id, requester_id, "board.collaborator.add", "user", target.id)
    return collab


async def remove_collaborator(
    db: AsyncSession,
    board_id: str,
    requester_id: str,
    target_user_id: str,
) -> None:
    await assert_board_access(db, board_id, requester_id, require_role="admin")
    result = await db.execute(
        select(BoardCollaborator).where(
            BoardCollaborator.board_id == board_id,
            BoardCollaborator.user_id  == target_user_id,
        )
    )
    collab = result.scalar_one_or_none()
    if not collab:
        raise HTTPException(404, "Collaborator not found")
    await db.delete(collab)
    _audit(db, board_id, requester_id, "board.collaborator.remove", "user", target_user_id)


# ── Internal ──────────────────────────────────────────────────────────────────

def _audit(
    db: AsyncSession,
    board_id: str,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    diff: Optional[dict] = None,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
) -> None:
    db.add(AuditLog(
        board_id=board_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        diff=diff,
        ip_address=ip,
        user_agent=ua,
    ))
