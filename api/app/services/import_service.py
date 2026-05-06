"""
Import service — extracts board structure from uploaded PDF or image via
Google Gemini's multimodal API, then commits the result to the board.

Runs synchronously (Vercel Option A): POST /import blocks until extraction is
complete. The DB job record is kept so the poll endpoint stays contractually
compatible with a future async approach.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from google import genai
from google.genai import types
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Board, Element, ImportJob, Upload
from app.services.upload_service import download_bytes

log = logging.getLogger(__name__)
settings = get_settings()
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


DAILY_IMPORT_LIMIT = 5
_EXTRACTION_PROMPT = """\
You are analysing an image or PDF of a service blueprint, journey map, or process diagram.

Extract the visible structure into JSON with this exact schema:

{
  "title":    string,
  "domain":   string | null,
  "confidence": "high" | "medium" | "low",
  "notes":    string,
  "swimlanes": [{"name": string, "order": int}],
  "steps":     [{"name": string, "order": int}],
  "elements": [
    {
      "swimlane_name": string,
      "step_name":     string,
      "type":          "customer_action" | "physical_evidence" | "frontstage_action" | "backstage_action" | "support_process" | "moment_of_truth" | "touchpoint" | "system" | "data_flow" | "handoff" | "risk" | "opportunity" | "pain_point" | "ai_capability" | "governance_checkpoint",
      "name":          string,
      "notes":         string | null
    }
  ]
}

Rules:
- Extract only what's visible. Don't invent content.
- If you can't determine the type of an element, use "touchpoint" as default.
- Map visible elements to canonical types: actions the customer takes -> customer_action; interfaces/forms/documents the customer sees -> physical_evidence; actions employees do in front of customers -> frontstage_action; actions employees do out of sight -> backstage_action; internal systems, queues, or IT support -> support_process; critical decision points for service success -> moment_of_truth.
- Map visual styling: red/warning shapes -> risk; green -> opportunity; boxes with code/API labels -> system; human icons performing a visible service action -> frontstage_action.
- If the blueprint has more than 10 swimlanes or 15 steps, cap at those limits and note what was truncated.
- Set confidence "low" if the image is blurry, handwritten, or ambiguous.
- Return ONLY the JSON. No markdown fences, no prose.\
"""


# ── Daily limit ───────────────────────────────────────────────────────────────

async def _count_imports_today(db: AsyncSession, user_id: str) -> int:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    res = await db.execute(
        select(func.count(ImportJob.id)).where(
            ImportJob.user_id == user_id,
            ImportJob.created_at >= today,
        )
    )
    return res.scalar() or 0


# ── Extraction ────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def _run_extraction(file_bytes: bytes, content_type: str) -> tuple[Optional[dict], int]:
    """Call Gemini with the extraction prompt. Retries once on JSON parse failure."""
    for attempt in range(2):
        response = await _get_client().aio.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=content_type,
                                data=file_bytes,
                            )
                        ),
                        types.Part(text=_EXTRACTION_PROMPT),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                max_output_tokens=4096,
            ),
        )
        tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
        raw    = response.text or ""
        parsed = _parse_json(raw)
        if parsed is not None:
            return parsed, tokens
        log.warning("Extraction attempt %d: JSON parse failed. Raw: %.200s", attempt + 1, raw)

    return None, 0


def _validate_result(result: dict) -> str:
    """Return 'done' or 'partial' depending on extraction quality."""
    required = {"swimlanes", "steps", "elements"}
    if not required.issubset(result.keys()):
        return "partial"
    elements = result.get("elements", [])
    has_warning = any(
        e.get("swimlane_name") not in [s["name"] for s in result.get("swimlanes", [])] or
        e.get("step_name") not in [s["name"] for s in result.get("steps", [])]
        for e in elements
    )
    if has_warning or result.get("confidence") == "low":
        return "partial"
    return "done"


# ── Public API ────────────────────────────────────────────────────────────────

async def start_import(
    db:        AsyncSession,
    board_id:  str,
    user_id:   str,
    upload_id: str,
) -> ImportJob:
    count = await _count_imports_today(db, user_id)
    if count >= DAILY_IMPORT_LIMIT:
        raise HTTPException(429, "Daily import limit reached (5 per day).")

    board_res = await db.execute(select(Board).where(Board.id == board_id))
    board = board_res.scalar_one_or_none()
    if not board:
        raise HTTPException(404, "Board not found.")
    state = board.state or {}
    has_lanes = bool(state.get("swimlanes"))
    has_steps = bool(state.get("steps"))
    elem_count_res = await db.execute(
        select(func.count(Element.id)).where(Element.board_id == board_id)
    )
    elem_count = elem_count_res.scalar() or 0
    if has_lanes or has_steps or elem_count > 0:
        raise HTTPException(409, "Board already has content. Create a new board to import into instead.")

    upload_res = await db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.board_id == board_id)
    )
    upload = upload_res.scalar_one_or_none()
    if not upload:
        raise HTTPException(404, "Upload not found on this board.")

    job = ImportJob(
        board_id=board_id,
        upload_id=upload_id,
        user_id=user_id,
        status="processing",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    try:
        file_bytes = await download_bytes(upload.storage_path)
        result, tokens = await _run_extraction(file_bytes, upload.content_type)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Import extraction error: %s", exc)
        job.status = "failed"
        job.error = str(exc)[:500]
        job.completed_at = datetime.now(timezone.utc)
        return job

    if result is None:
        job.status = "failed"
        job.error = "We couldn't automatically extract the blueprint from this file. You can start from scratch or try a clearer image."
        job.completed_at = datetime.now(timezone.utc)
        job.token_count = tokens
        return job

    job.status = _validate_result(result)
    job.result = result
    job.token_count = tokens
    job.completed_at = datetime.now(timezone.utc)
    log.info("Import job %s finished: status=%s tokens=%d", job.id, job.status, tokens)
    return job


async def get_import_job(
    db:       AsyncSession,
    board_id: str,
    job_id:   str,
) -> ImportJob:
    res = await db.execute(
        select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.board_id == board_id,
        )
    )
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Import job not found.")
    return job


async def accept_import(
    db:       AsyncSession,
    board_id: str,
    job_id:   str,
    user_id:  str,
    edits:    Optional[dict] = None,
) -> dict:
    job = await get_import_job(db, board_id, job_id)
    if job.status not in ("done", "partial"):
        raise HTTPException(409, f"Cannot accept an import job with status '{job.status}'.")

    data = edits if edits is not None else job.result
    if not data:
        raise HTTPException(422, "No extraction result to commit.")

    raw_swimlanes = data.get("swimlanes", [])
    raw_steps     = data.get("steps", [])
    raw_elements  = data.get("elements", [])

    lane_id_map = {sl["name"]: str(uuid.uuid4()) for sl in raw_swimlanes}
    step_id_map = {st["name"]: str(uuid.uuid4()) for st in raw_steps}

    swimlanes = [
        {"id": lane_id_map[sl["name"]], "name": sl["name"], "order": sl.get("order", i)}
        for i, sl in enumerate(raw_swimlanes)
    ]
    steps = [
        {"id": step_id_map[st["name"]], "name": st["name"], "order": st.get("order", i)}
        for i, st in enumerate(raw_steps)
    ]

    board_res = await db.execute(select(Board).where(Board.id == board_id))
    board = board_res.scalar_one_or_none()
    if not board:
        raise HTTPException(404, "Board not found.")
    board.state = {**board.state, "swimlanes": swimlanes, "steps": steps}
    board.version += 1

    if data.get("title") and board.title in ("Untitled Blueprint", "Untitled"):
        board.title = data["title"][:500]

    for elem in raw_elements:
        lane_id = lane_id_map.get(elem.get("swimlane_name", ""))
        step_id = step_id_map.get(elem.get("step_name", ""))
        el = Element(
            board_id=board_id,
            swimlane_id=lane_id,
            step_id=step_id,
            type=elem.get("type", "touchpoint"),
            name=elem.get("name", "Unnamed element")[:200],
            notes=elem.get("notes"),
            status="draft",
        )
        db.add(el)

    await db.flush()
    return {"success": True, "board_id": board_id}


async def discard_import(
    db:       AsyncSession,
    board_id: str,
    job_id:   str,
    user_id:  str,
) -> None:
    job = await get_import_job(db, board_id, job_id)
    await db.delete(job)
    await db.flush()
