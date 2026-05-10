"""
Agent router -- /api/agent/*
POST /api/agent/chat              -> call Gemini, persist, return response
GET  /api/agent/boards/{id}/history -> paginated chat history
DELETE /api/agent/boards/{id}/history -> clear history
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

from app.database import get_db
from app.models import ChatMessage, User
from app.schemas import ChatRequest, ChatResponse, ChatMessageOut, AgentCallError
from app.services import agent_service
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, body.board_id, user.id)

    history = [{"role": h.role, "content": h.content} for h in body.history]

    try:
        text, tokens, msg_id = await agent_service.chat(
            db, body.board_id, user.id, body.message, history,
            role=body.role,
            attachment_ids=body.attachments,
        )
    except AgentCallError as exc:
        # Return a structured 200 so the client renders an inline error card
        # rather than treating it as a network failure.
        return ChatResponse(error=exc.error)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Unexpected error in /api/agent/chat: %s", exc, exc_info=True)
        raise HTTPException(500, f"Chat failed unexpectedly: {type(exc).__name__}")

    return ChatResponse(response=text, token_count=tokens, message_id=msg_id)


@router.get("/boards/{board_id}/history", response_model=list[ChatMessageOut])
async def get_history(
    board_id: str,
    limit:    int = 50,
    offset:   int = 0,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)

    if not 1 <= limit <= 200:
        raise HTTPException(400, "limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")

    result = await db.execute(
        select(ChatMessage)
        .options(selectinload(ChatMessage.user))
        .where(ChatMessage.board_id == board_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = list(reversed(result.scalars().all()))
    return [
        ChatMessageOut(
            id=str(m.id),
            role=m.role,
            content=m.content,
            attachments=m.attachments or [],
            created_at=m.created_at,
            author_name=m.user.full_name if m.user else None,
        )
        for m in messages
    ]


@router.delete("/boards/{board_id}/history", status_code=204)
async def clear_history(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id, require_role="editor")
    await db.execute(
        sql_delete(ChatMessage).where(ChatMessage.board_id == board_id)
    )
    await db.commit()
