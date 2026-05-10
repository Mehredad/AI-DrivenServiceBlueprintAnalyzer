"""
Agent service -- builds a board-aware system prompt from live DB state,
calls the Google Gemini API server-side (key never leaves server),
persists both turns of the conversation.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
except ImportError:  # CI / test environment without google-genai installed
    genai         = None  # type: ignore[assignment]
    types         = None  # type: ignore[assignment]
    genai_errors  = None  # type: ignore[assignment]

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Board, Capability, Element, Insight, GovernanceDecision, ChatMessage, Upload
from app.schemas import AgentError, AgentCallError
from app.services.error_messages import USER_MESSAGES, RETRY_ADVICE

log = logging.getLogger(__name__)

settings = get_settings()
_client = None

# In-memory consecutive-failure counter for /health/agent.
# NOTE: Resets on cold start -- each Vercel invocation may be a fresh process,
# so this counter is only meaningful within a warm instance.
_consecutive_failures: int = 0
_last_error_code: Optional[str] = None


def _get_client():
    global _client
    if genai is None:
        raise HTTPException(503, "AI service unavailable: google-genai package not installed.")
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


MAX_HISTORY_MESSAGES = 20
MAX_RESPONSE_TOKENS  = 1024


# -- Health counter ------------------------------------------------------------

def get_health_state() -> dict:
    """Return current health status for GET /health/agent."""
    global _consecutive_failures, _last_error_code
    if _consecutive_failures == 0:
        status = "ok"
    elif _consecutive_failures < 5:
        status = "degraded"
    else:
        status = "down"
    return {
        "status":     status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "last_error": _last_error_code,
    }


# -- Error classification ------------------------------------------------------

def _classify_error(exc: Exception, request_id: str) -> AgentError:
    """
    Map a google-genai SDK exception to a user-facing AgentError.

    The SDK (google-genai >= 1.0) raises google.genai.errors.ClientError for
    4xx responses and google.genai.errors.ServerError for 5xx -- NOT the
    google.api_core.exceptions hierarchy referenced in older SDK docs.
    Each exception has .code (int HTTP status) and .status (str e.g. RESOURCE_EXHAUSTED).
    """
    code = "unknown"

    if genai_errors is not None:
        if isinstance(exc, genai_errors.ClientError):
            http_code  = getattr(exc, "code", 0)
            status_str = str(getattr(exc, "status", "") or "").upper()
            if http_code == 429:
                # RESOURCE_EXHAUSTED on free tier = daily quota; other 429 = rate limit
                if "RESOURCE_EXHAUSTED" in status_str or "QUOTA" in status_str:
                    code = "quota_exhausted"
                else:
                    code = "rate_limited"
            elif http_code in (401, 403):
                code = "auth_failure"
            elif http_code == 400:
                code = "invalid_request"
            else:
                code = "unknown"
        elif isinstance(exc, genai_errors.ServerError):
            code = "service_unavailable"

    return AgentError(
        code=code,
        user_message=USER_MESSAGES[code],
        retry_advice=RETRY_ADVICE[code],
        request_id=request_id,
    )


# -- Board context builder -----------------------------------------------------

async def build_board_context(db: AsyncSession, board_id: str) -> dict:
    """Pull live board state from every relevant table and return as a dict."""
    board_res = await db.execute(select(Board).where(Board.id == board_id))
    board = board_res.scalar_one_or_none()
    if not board:
        return {}

    caps_res = await db.execute(
        select(Capability).where(Capability.board_id == board_id).order_by(Capability.cap_id)
    )
    caps = caps_res.scalars().all()

    elems_res = await db.execute(
        select(Element)
        .where(Element.board_id == board_id)
        .order_by(Element.updated_at.desc())
        .limit(20)
    )
    elements = elems_res.scalars().all()

    open_ins_res = await db.execute(
        select(Insight).where(
            Insight.board_id     == board_id,
            Insight.is_dismissed.is_(False),
        ).order_by(Insight.generated_at.desc()).limit(10)
    )
    open_insights = open_ins_res.scalars().all()

    gov_res = await db.execute(
        select(GovernanceDecision)
        .where(GovernanceDecision.board_id == board_id)
        .order_by(GovernanceDecision.decided_at.desc())
        .limit(5)
    )
    recent_gov = gov_res.scalars().all()

    return {
        "board_id":      board.id,
        "title":         board.title,
        "domain":        board.domain,
        "current_phase": board.phase,
        "version":       board.version,
        "board_state":   board.state,
        "capabilities": [
            {
                "cap_id":       c.cap_id,
                "name":         c.name,
                "type":         c.type,
                "risk_level":   c.risk_level,
                "frontstage":   c.frontstage,
                "xai_strategy": c.xai_strategy,
                "autonomy":     c.autonomy,
                "status":       c.status,
                "owner":        c.owner,
            }
            for c in caps
        ],
        "elements": [
            {
                "id":     str(e.id),
                "type":   e.type,
                "name":   e.name,
                "status": e.status,
                "owner":  e.owner,
            }
            for e in elements
        ],
        "open_insights": [
            {"severity": i.severity, "title": i.title, "source": i.source_ref}
            for i in open_insights
        ],
        "recent_governance_decisions": [
            {
                "type":       g.decision_type,
                "title":      g.title,
                "decided_at": str(g.decided_at),
            }
            for g in recent_gov
        ],
    }


# -- System prompt builder -----------------------------------------------------

def _has_ai_content(ctx: dict) -> bool:
    if ctx.get("capabilities"):
        return True
    return any(e.get("type") == "ai_capability" for e in ctx.get("elements", []))


def _core_section(ctx: dict) -> str:
    ctx_json = json.dumps(ctx, indent=2, default=str)
    return f"""You are the Blueprint Agent -- an expert collaborator embedded in Blueprint AI, a tool for mapping end-to-end system journeys across stakeholders, services, and systems.

You have real-time access to the current board:

{ctx_json}

Your responsibilities:
1. Help users understand and improve this specific board. Always reference actual elements, swimlanes, and steps by name.
2. Identify gaps, risks, and opportunities grounded in what is actually on the board.
3. Suggest concrete, actionable next steps -- not generic best practices.
4. When asked, draft governance notes, risk summaries, or documentation based on the board content.
5. This board may or may not involve AI. Do not assume AI is present unless you see AI capabilities or AI-tagged elements in the board state.

Communication:
- Be specific. Reference element IDs and names.
- Be brief. 150-300 words unless asked for more.
- Use bullets for multiple items, **bold** for key terms."""


def _hcai_section() -> str:
    return """This board contains AI capabilities. Apply Human-Centred AI (HCAI) considerations where relevant:
- **Transparency**: Are decisions explainable to affected stakeholders? Is there an XAI strategy for each AI capability?
- **Autonomy**: What is the human override mechanism? Is the autonomy level appropriate for the risk level?
- **Harm patterns**: Flag potential fairness, accountability, or digital wellbeing concerns proactively."""


_ROLE_SECTIONS: dict[str, str] = {
    "pm":         "The user is a Product Manager. Emphasise priorities, risks, open decisions, and opportunities. Ask them about user outcomes and business impact.",
    "designer":   "The user is a Service or UX Designer. Emphasise touchpoints, handoffs, and journey friction. Ask about stakeholder experience.",
    "researcher": "The user is a UX Researcher. Emphasise pain points, evidence gaps, and unvalidated assumptions. Ask what research has been done.",
    "developer":  "The user is a Developer. Emphasise systems, data flows, APIs, and technical risks. Ask about integration and operational concerns.",
    "delivery":   "The user is a Delivery Lead. Emphasise status, dependencies, and sequencing risks. Ask about milestones and blockers.",
    "governance": "The user is a Governance or Compliance Officer. Emphasise risks, audit trails, decision documentation, and compliance gaps. Ask about accountability and oversight.",
}


def _role_section(role: str) -> str:
    text = _ROLE_SECTIONS.get(role)
    if not text:
        return ""
    return f"Role context: {text}"


def build_system_prompt(ctx: dict, role: Optional[str] = None) -> str:
    sections = [_core_section(ctx)]
    if _has_ai_content(ctx):
        sections.append(_hcai_section())
    if role:
        section = _role_section(role)
        if section:
            sections.append(section)
    return "\n\n".join(sections)


# -- Message format helpers ----------------------------------------------------

def _history_to_gemini(history: list[dict]) -> list[types.Content]:
    """Convert stored message history to Gemini Content objects."""
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        text = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents


async def _build_user_parts(
    db: AsyncSession, attachment_ids: list[str], board_id: str, text: str
) -> tuple[list[types.Part], list[dict]]:
    """
    Fetch attached files and build Gemini Part objects (images and PDFs supported).
    Falls back gracefully if storage is not configured or a file fails.
    """
    from app.services.upload_service import download_bytes

    parts: list[types.Part] = []
    attach_refs: list[dict] = []

    if attachment_ids:
        uploads_res = await db.execute(
            select(Upload).where(
                Upload.id.in_(attachment_ids),
                Upload.board_id == board_id,
            )
        )
        uploads = uploads_res.scalars().all()

        for up in uploads:
            attach_refs.append({
                "upload_id":    str(up.id),
                "filename":     up.filename,
                "content_type": up.content_type,
            })
            try:
                file_bytes = await download_bytes(up.storage_path)
                parts.append(types.Part(
                    inline_data=types.Blob(
                        mime_type=up.content_type,
                        data=file_bytes,
                    )
                ))
            except Exception as exc:
                log.warning("Could not fetch attachment %s: %s", up.id, exc)

    parts.append(types.Part(text=text))
    return parts, attach_refs


# -- Main chat function --------------------------------------------------------

async def chat(
    db:             AsyncSession,
    board_id:       str,
    user_id:        str,
    message:        str,
    history:        list[dict],
    role:           Optional[str] = None,
    attachment_ids: list[str] = [],
) -> tuple[str, int, str]:
    """
    Call Gemini API with board-aware system prompt.
    Persists user turn immediately; persists assistant turn on success only.
    Returns (response_text, total_tokens_used, assistant_message_id).
    Raises AgentCallError on any AI service failure.
    """
    global _consecutive_failures, _last_error_code

    if types is None:
        raise HTTPException(503, "AI service unavailable: google-genai package not installed.")

    request_id = str(uuid.uuid4())

    ctx     = await build_board_context(db, board_id)
    system  = build_system_prompt(ctx, role=role)
    trimmed = history[-MAX_HISTORY_MESSAGES:]

    if attachment_ids:
        user_parts, attach_refs = await _build_user_parts(
            db, attachment_ids, board_id, message
        )
    else:
        user_parts  = [types.Part(text=message)]
        attach_refs = []

    # Persist user message before LLM call (FR-7: user message survives AI errors).
    # commit() not flush() so the row is durable even when the LLM call fails and
    # the session never reaches its end-of-request commit.
    user_msg = ChatMessage(
        board_id=board_id, user_id=user_id, role="user",
        content=message, attachments=attach_refs,
    )
    db.add(user_msg)
    await db.commit()

    contents = _history_to_gemini(trimmed) + [
        types.Content(role="user", parts=user_parts)
    ]

    try:
        response = await _get_client().aio.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=MAX_RESPONSE_TOKENS,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _consecutive_failures += 1
        agent_error = _classify_error(exc, request_id)
        _last_error_code = agent_error.code
        log.error(
            "Gemini API error (request_id=%s board=%s user=%s code=%s): %s: %s",
            request_id, board_id, user_id, agent_error.code,
            type(exc).__name__, exc,
        )
        raise AgentCallError(error=agent_error) from exc

    _consecutive_failures = 0
    _last_error_code = None

    text   = response.text or ""
    tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0

    log.info("Chat tokens used: %d (board=%s, attachments=%d)", tokens, board_id, len(attach_refs))

    asst_msg = ChatMessage(
        board_id=board_id, user_id=None, role="assistant",
        content=text, token_count=tokens,
    )
    db.add(asst_msg)
    await db.flush()

    return text, tokens, str(asst_msg.id)
