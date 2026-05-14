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
from app.models import Board, Capability, Connector, Element, Insight, GovernanceDecision, ChatMessage, Upload
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
MAX_RESPONSE_TOKENS  = 8192


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

_CONNECTOR_FULL_LIMIT = 100


def _resolve_endpoint(
    step_id, element_id,
    step_map: dict[str, str],
    element_map: dict[str, str],
) -> dict:
    if step_id:
        sid = str(step_id)
        return {"kind": "step", "id": sid, "name": step_map.get(sid, sid)}
    eid = str(element_id)
    return {"kind": "element", "id": eid, "name": element_map.get(eid, eid)}


def _serialize_connector(c: "Connector", step_map: dict, element_map: dict) -> dict:
    return {
        "id":     str(c.id),
        "source": _resolve_endpoint(c.source_step_id, c.source_element_id, step_map, element_map),
        "target": _resolve_endpoint(c.target_step_id, c.target_element_id, step_map, element_map),
        "type":   c.connector_type,
        "tier":   c.tier,
        "label":  c.label,
    }


def _build_connector_context(
    connectors: list,
    all_elements: list,
    step_map: dict[str, str],
    element_map: dict[str, str],
) -> dict:
    """Return full list or summary dict depending on connector count."""
    if len(connectors) <= _CONNECTOR_FULL_LIMIT:
        return {
            "connectors": [_serialize_connector(c, step_map, element_map) for c in connectors]
        }

    # Summary mode for large boards
    by_type: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    connected_ids: set[str] = set()
    target_ids: set[str]  = set()
    source_ids: set[str]  = set()

    for c in connectors:
        by_type[c.connector_type] = by_type.get(c.connector_type, 0) + 1
        by_tier[c.tier]           = by_tier.get(c.tier, 0) + 1
        for fld in (c.source_element_id, c.target_element_id,
                    c.source_step_id,    c.target_step_id):
            if fld:
                connected_ids.add(str(fld))
        if c.target_element_id:
            target_ids.add(str(c.target_element_id))
        if c.source_element_id:
            source_ids.add(str(c.source_element_id))

    orphaned = [
        {"id": str(e.id), "name": e.name}
        for e in all_elements
        if str(e.id) not in connected_ids
    ][:10]

    dead_ends = [
        {"id": str(e.id), "name": e.name}
        for e in all_elements
        if str(e.id) in target_ids and str(e.id) not in source_ids
    ][:10]

    return {
        "connectors_summary": {
            "total":              len(connectors),
            "by_type":            by_type,
            "by_tier":            by_tier,
            "orphaned_elements":  orphaned,
            "dead_ends":          dead_ends,
        },
        "connectors_sample": [
            _serialize_connector(c, step_map, element_map)
            for c in connectors[-20:]
        ],
    }


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

    # Fetch all elements — need all for connector name resolution; display is capped at 20.
    elems_res = await db.execute(
        select(Element)
        .where(Element.board_id == board_id)
        .order_by(Element.updated_at.desc())
    )
    all_elements = elems_res.scalars().all()
    elements = all_elements[:20]

    conn_res = await db.execute(
        select(Connector)
        .where(Connector.board_id == board_id)
        .order_by(Connector.created_at)
    )
    connectors = conn_res.scalars().all()

    element_map = {str(e.id): e.name for e in all_elements}
    step_map    = {
        str(s["id"]): s.get("name", "")
        for s in (board.state or {}).get("steps", [])
        if "id" in s
    }

    # Partition elements: placed = visible on canvas (has both swimlane_id AND step_id).
    # Orphaned = exist in DB but are invisible because they have no placement.
    placed_elements   = [e for e in all_elements if e.swimlane_id and e.step_id]
    orphaned_elements = [e for e in all_elements if not e.swimlane_id or not e.step_id]

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

    connector_ctx = _build_connector_context(connectors, all_elements, step_map, element_map)

    return {
        "board_id":      board.id,
        "title":         board.title,
        "domain":        board.domain,
        "current_phase": board.phase,
        "version":       board.version,
        "board_state":   board.state,
        # IMPORTANT: only placed_elements are VISIBLE on the canvas.
        # Orphaned elements exist in the DB but have no swimlane+step placement
        # and are completely invisible to users. Do NOT tell the user the board
        # contains elements unless placed_count > 0.
        "canvas_summary": {
            "placed_element_count":  len(placed_elements),
            "orphaned_element_count": len(orphaned_elements),
            "swimlane_count":        len((board.state or {}).get("swimlanes", [])),
            "step_count":            len((board.state or {}).get("steps", [])),
        },
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
            for e in placed_elements[:20]
        ],
        # Unplaced elements exist in the DB but are NOT visible on the canvas.
        # Use update_element with swimlane_id + step_id to place them.
        # Never use create_element for these — that would create duplicates.
        "unplaced_elements": [
            {
                "id":   str(e.id),
                "type": e.type,
                "name": e.name,
            }
            for e in orphaned_elements
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
        **connector_ctx,
    }


# -- System prompt builder -----------------------------------------------------

def _has_ai_content(ctx: dict) -> bool:
    if ctx.get("capabilities"):
        return True
    return any(e.get("type") == "ai_capability" for e in ctx.get("elements", []))


def _placement_reference(ctx: dict) -> str:
    """Build a compact swimlane/step ID reference the agent must copy verbatim."""
    state = ctx.get("board_state") or {}
    swimlanes = state.get("swimlanes", [])
    steps     = state.get("steps", [])
    if not swimlanes and not steps:
        return ""
    lines = ["", "## PLACEMENT REFERENCE — copy these IDs verbatim when proposing create_element actions. Do NOT invent, modify, or guess IDs.", ""]
    if swimlanes:
        lines.append("Swimlanes (swimlane_id):")
        for sl in swimlanes:
            lines.append(f'  "{sl.get("name","")}"  →  "{sl.get("id","")}"')
    if steps:
        lines.append("Steps (step_id):")
        for st in steps:
            lines.append(f'  "{st.get("name","")}"  →  "{st.get("id","")}"')
    lines.append("")
    return "\n".join(lines)


def _core_section(ctx: dict) -> str:
    ctx_json = json.dumps(ctx, indent=2, default=str)
    placement_ref = _placement_reference(ctx)
    return f"""You are the Blueprint Agent -- an expert collaborator embedded in Blueprint AI, a tool for mapping end-to-end system journeys across stakeholders, services, and systems.

You have real-time access to the current board:

{ctx_json}
{placement_ref}
Your responsibilities:
1. Help users understand and improve this specific board. Always reference actual elements, swimlanes, and steps by name.
2. Identify gaps, risks, and opportunities grounded in what is actually on the board.
3. Suggest concrete, actionable next steps -- not generic best practices.
4. When asked, draft governance notes, risk summaries, or documentation based on the board content.
5. This board may or may not involve AI. Do not assume AI is present unless you see AI capabilities or AI-tagged elements in the board state.

Communication:
- Be specific. Reference element names and IDs.
- For simple questions, be concise (a few sentences). For gap analysis, reviews, or strategy questions, be thorough and complete — never cut off mid-point.
- Use bullets for multiple items, **bold** for key terms, ### for section headings.
- Never include raw JSON, code blocks, or technical object notation in your response. Write everything as plain prose or structured markdown.
- End every response with a short "**What to do next:**" section offering 2-3 concrete next steps the user can take on this board."""


def _hcai_section() -> str:
    return """This board contains AI capabilities. Apply Human-Centred AI (HCAI) considerations where relevant:
- **Transparency**: Are decisions explainable to affected stakeholders? Is there an XAI strategy for each AI capability?
- **Autonomy**: What is the human override mechanism? Is the autonomy level appropriate for the risk level?
- **Harm patterns**: Flag potential fairness, accountability, or digital wellbeing concerns proactively."""


_ACTIONS_SECTION = """## Board edit actions

When the user asks you to make changes to the board, respond ONLY with a JSON object in this exact format:

{
  "message": "Your explanation in plain language (Markdown supported)",
  "actions": [
    { "type": "create_swimlane", "payload": { "name": "AI Capabilities", "lane_type": "support_processes" } }
  ]
}

Allowed action types and their payloads:
- create_swimlane: { "name": "...", "lane_type": "customer_actions|frontstage_actions|backstage_actions|support_processes|moment_of_truth|touchpoints|systems|data_flow|handoffs|risks|opportunities|pain_points|ai_capability|research_evidence|governance|custom" }
- create_step: { "name": "..." }
- create_element: { "type": "customer_action|physical_evidence|frontstage_action|backstage_action|support_process|moment_of_truth|touchpoint|system|data_flow|handoff|risk|opportunity|pain_point|research_evidence|ai_capability|governance_checkpoint", "name": "...", "swimlane_id": "<REQUIRED — exact UUID from PLACEMENT REFERENCE above, swimlane_id column>", "step_id": "<REQUIRED — exact UUID from PLACEMENT REFERENCE above, step_id column>", "notes": "..." }
- update_element: { "id": "...", "name": "...", "updates": { "name": "...", "notes": "...", "status": "...", "swimlane_id": "...", "step_id": "..." } }
  → To place an unplaced element on the canvas: use update_element with updates.swimlane_id and updates.step_id copied from the PLACEMENT REFERENCE. Copy the element id from unplaced_elements[]. NEVER use create_element for elements already in unplaced_elements — that creates duplicates.
- delete_element: { "id": "...", "name": "..." }
- update_swimlane: { "id": "...", "name": "..." }
- delete_swimlane: { "id": "...", "name": "..." }
- update_step: { "id": "...", "name": "..." }
- delete_step: { "id": "...", "name": "..." }
- create_connector: { "source": {"kind": "element"|"step", "id": "..."}, "target": {"kind": "element"|"step", "id": "..."}, "connector_type": "sequence"|"data_flow"|"trigger"|"dependency"|"feedback"|"failure", "label": "optional string", "rationale": "why you are proposing this — shown to the user" }
- update_connector: { "connector_id": "...", "updates": { "connector_type": "...", "label": "...", "notes": "..." }, "rationale": "..." }
- delete_connector: { "connector_id": "...", "rationale": "..." }

Rules:
- Never claim to have made a change — only propose it. The user must approve each action before it is applied.
- Put your full explanation in the "message" field. Explain each proposed action.
- For analysis, questions, or reviews: respond with plain Markdown prose only — absolutely no JSON, no code blocks, no technical object notation.
- For create_element: swimlane_id and step_id are REQUIRED. Copy them exactly from the PLACEMENT REFERENCE section above. NEVER generate, invent, or guess UUID values — if you are not certain of the correct ID, do not propose the action.
- Reference real IDs from the board context (board_state.swimlanes[].id, board_state.steps[].id, elements[].id) for ALL other actions. NEVER use a name as an ID.
- Reference real connector IDs from the connectors list when proposing update_connector or delete_connector.
- For create_connector: use real element or step IDs from the board context as source/target.
- Each action is independent — the user can approve some and reject others.
- Do not propose more than 5 connector actions in a single response — prioritise the most impactful gaps.

Example — good connector proposal response:
{
  "message": "The login form connects to the backend via data_flow, but there is no failure path back. If auth fails, users won't know why. I'm proposing a failure connector.",
  "actions": [
    {
      "type": "create_connector",
      "payload": {
        "source": {"kind": "element", "id": "<backend-element-id>"},
        "target": {"kind": "element", "id": "<login-form-element-id>"},
        "connector_type": "failure",
        "label": "invalid credentials",
        "rationale": "Without a failure path, auth errors are invisible to the user. This connector makes the error flow explicit."
      }
    }
  ]
}"""


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


def _connectors_section(ctx: dict) -> str:
    """Generate a system prompt section that teaches the agent to use connector data."""
    if "connectors_summary" in ctx:
        s = ctx["connectors_summary"]
        orphaned_names = [o["name"] for o in s.get("orphaned_elements", [])]
        dead_end_names = [d["name"] for d in s.get("dead_ends", [])]
        return (
            f"This board has {s['total']} connectors (summary mode — board is large).\n"
            f"By type: {s['by_type']}\n"
            f"By tier: {s['by_tier']}\n"
            f"Orphaned elements (zero connectors): {orphaned_names or 'none'}\n"
            f"Dead-end elements (incoming only, no outgoing): {dead_end_names or 'none'}\n"
            "A representative sample of connectors is included in the board context.\n\n"
            + _CONNECTOR_REASONING_RULES
        )

    connectors = ctx.get("connectors", [])
    if not connectors:
        return (
            "This board has no connectors yet. "
            "Do not hallucinate connections between elements. "
            "If asked about flows or relationships, acknowledge that no connectors have been drawn and invite the user to add them."
        )

    return (
        f"This board has {len(connectors)} typed, directed connectors between its steps and elements.\n"
        "Each connector has a source, a target (step or element), a type "
        "(sequence | data_flow | trigger | dependency | feedback | failure), "
        "a tier (step | element | mixed), and an optional label.\n\n"
        + _CONNECTOR_REASONING_RULES
    )


_CONNECTOR_REASONING_RULES = """\
When reasoning about the board:
- Use connectors to trace flow — do not rely on element placement alone.
- Reference connectors using the format: [connector: Source Name → Target Name (type)]
  Example: [connector: Login form → Backend auth service (data_flow)]
- Only reference connectors that exist in the provided context. Never invent connections.
- Identify orphaned elements (zero connectors) — they may be incomplete or not yet wired in.
- Identify missing failure paths: steps or elements with no 'failure' connector out.
- Flag data flows that cross visibility lines (frontstage → backstage) — may need transparency review.
- Note bottlenecks: elements with many incoming 'dependency' connectors are single points of failure.
- Note cycles (A → B → C → A) — sometimes intentional (retry loops), often a design smell.

When proposing connector changes (via the action vocabulary):
- Propose create_connector when: an element has no outgoing connectors but clearly leads somewhere; a high-stakes step has no failure path; a data flow is implied by element placement but not drawn.
- Propose update_connector when: an existing connector is mis-typed (e.g. sequence where failure is appropriate) or has a misleading or missing label.
- Propose delete_connector when: a connector is redundant (duplicate path) or contradicts the described flow.
- Always include a rationale field — the user reads it before deciding to approve.
- Never propose more than 5 connector actions per response. If many gaps exist, prioritise and offer to surface more next turn.

Good response examples:
- "The login form has a data_flow to the backend, but I see no failure connector from the backend back [connector: Backend auth → Login form (failure)] — how are auth errors communicated to users?"
- "Two elements have no connectors at all: 'X' and 'Y'. Are they orphaned, or not yet wired?"
- "Three elements depend on 'Auth service' via dependency connectors — it's a single point of failure. Consider a fallback."
- "If no feedback connector exists on this board, I'll note it honestly rather than assume one is present.\""""


def _parse_agent_response(text: str) -> tuple[str, list[dict]]:
    """
    Try to parse agent response as structured JSON {"message": ..., "actions": [...]}.
    Handles:
      1. Entire response is a bare JSON object.
      2. JSON wrapped in a markdown code fence (```json ... ```).
      3. JSON object embedded anywhere in the text (model mixed prose + JSON).
    Falls back to (text, []) if not parseable or missing the expected shape.
    """
    import re

    def _extract_actions(data: dict) -> tuple[str, list[dict]] | None:
        if isinstance(data, dict) and isinstance(data.get('message'), str):
            actions = data.get('actions', [])
            if isinstance(actions, list):
                valid = [
                    a for a in actions
                    if isinstance(a, dict)
                    and isinstance(a.get('type'), str)
                    and isinstance(a.get('payload'), dict)
                ]
                return data['message'], valid
        return None

    stripped = text.strip()

    # Case 1: entire response is a bare JSON object
    if stripped.startswith('{'):
        try:
            result = _extract_actions(json.loads(stripped))
            if result:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Case 2: JSON wrapped in a markdown code fence
    m = re.search(r'```(?:json)?\s*(\{.*?})\s*```', stripped, re.DOTALL)
    if m:
        try:
            result = _extract_actions(json.loads(m.group(1)))
            if result:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Case 3: JSON object embedded in prose (model prepended explanation text)
    json_match = re.search(r'\{\s*"message"\s*:', stripped)
    if json_match:
        try:
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(stripped, json_match.start())
            result = _extract_actions(data)
            if result:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return text, []


def build_system_prompt(ctx: dict, role: Optional[str] = None) -> str:
    sections = [_core_section(ctx)]
    sections.append(_connectors_section(ctx))
    if _has_ai_content(ctx):
        sections.append(_hcai_section())
    if role:
        section = _role_section(role)
        if section:
            sections.append(section)
    sections.append(_ACTIONS_SECTION)
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
) -> tuple[str, int, str, list[dict]]:
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

    # Detect truncation: if the model was stopped by the token limit, append a hint
    try:
        finish_reason = response.candidates[0].finish_reason if response.candidates else None
        if finish_reason and str(finish_reason).upper() in ("MAX_TOKENS", "2"):
            text = text.rstrip() + "\n\n*Response reached length limit. Ask me to continue, or narrow your question.*"
    except Exception:
        pass

    log.info("Chat tokens used: %d (board=%s, attachments=%d)", tokens, board_id, len(attach_refs))

    # Parse structured JSON response ({message, actions}) if present.
    # Store the raw text (JSON) in DB so history can reconstruct proposal cards.
    display_text, actions = _parse_agent_response(text)

    asst_msg = ChatMessage(
        board_id=board_id, user_id=None, role="assistant",
        content=text, token_count=tokens,
    )
    db.add(asst_msg)
    await db.flush()

    return display_text, tokens, str(asst_msg.id), actions
