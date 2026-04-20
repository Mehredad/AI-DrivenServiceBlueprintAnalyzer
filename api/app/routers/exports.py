"""
Exports router — /api/boards/{board_id}/export/pdf|json
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.services import export_service
from app.services.board_service import assert_board_access
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/boards", tags=["exports"])


@router.post("/{board_id}/export/json")
async def export_json(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    try:
        data = await export_service.export_json(db, board_id, user.id)
        await db.commit()
    except NoResultFound:
        raise HTTPException(404, "Board not found")

    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="board-{board_id[:8]}.json"'},
    )


@router.post("/{board_id}/export/pdf")
async def export_pdf(
    board_id: str,
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    await assert_board_access(db, board_id, user.id)
    try:
        data = await export_service.export_pdf(db, board_id, user.id)
        await db.commit()
    except RuntimeError as e:
        raise HTTPException(501, str(e))
    except NoResultFound:
        raise HTTPException(404, "Board not found")
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {str(e)}")

    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="board-{board_id[:8]}.pdf"'},
    )
