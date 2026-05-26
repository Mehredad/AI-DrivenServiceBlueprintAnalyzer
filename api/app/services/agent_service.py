"""
Agent service — board-aware system prompt + multi-provider fallback.

Provider chain (tried in order, automatic failover on rate-limit):
  1. Groq        — Llama 3.3 70B, 128 K context, ~1 000 req/day free
  2. Cerebras    — Llama 3.3 70B, 8 K context (free tier), ~1 000 req/day free
  3. Gemini      — Gemini 2.5 Flash, 1 M context, ~1 500 req/day free

When all providers return HTTP 429 the user receives a clear
"try again in 24 hours" message.  Switching is invisible to the user;
history is automatically compacted when routing to Cerebras (8 K limit).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
except ImportError:          # CI / test environment
    genai        = None      # type: ignore[assignment]
    types        = None      # type: ignore[assignment]
    genai_errors = None      # type: ignore[assignment]

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Board, Capability, Connector, Element,
    Insight, GovernanceDecision, ChatMessage, Upload,
)
from app.schemas import AgentError, AgentCallError
from app.services.error_messages import USER_MESSAGES, RETRY_ADVICE

log      = logging.getLogger(__name__)
settings = get_settings()

_gemini_client = None

# In-memory failure counter for GET /health/agent.
# Resets on cold start — Vercel may spin up a fresh process per invocation.
_consecutive_failures: int  = 0
_last_error_code: Optional[str] = None

MAX_HISTORY_MESSAGES = 20
MAX_RESPONSE_TOKENS  = 8192


# ── Provider chain ─────────────────────────────────────────────────────────────

# context_chars = context_tokens × 4 (rough chars-per-token estimate).
# compact=True means use the condensed system prompt + trim history tightly.
_PROVIDERS: list[dict] = [
    {
        "name":          "groq",
        "url":           "https://api.groq.com/openai/v1/chat/completions",
        "model":         "llama-3.3-70b-versatile",
        "context_chars": 512_000,   # 128 K tokens
        "compact":       False,
    },
    {
        "name":          "cerebras",
        "url":           "https://api.cerebras.ai/v1/chat/completions",
        "model":         "llama-3.3-70b",
        "context_chars": 32_000,    # 8 K tokens — free-tier hard limit
        "compact":       True,
    },
    {
        "name":          "gemini",
        "url":           None,       # uses google-genai SDK
        "model":         None,       # from settings.gemini_model
        "context_chars": 4_000_000, # 1 M tokens
        "compact":       False,
    },
]


def _provider_key(name: str) -> str:
    if name == "groq":
        return settings.groq_api_key
    if name == "cerebras":
        return settings.cerebras_api_key
    return settings.gemini_api_key


# ── Gemini SDK client ──────────────────────────────────────────────────────────

def _get_gemini_client():
    global _gemini_client
    if genai is None:
        raise HTTPException(
            503, "AI service unavailable: google-genai package not installed."
        )
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


# ── Health counter ─────────────────────────────────────────────────────────────

def get_health_state() -> dict:
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


# ── Error classification ───────────────────────────────────────────────────────

def _is_rate_limit(exc: Exception) -> bool:
    """True when the provider signals a rate-limit / quota exhaustion."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 529)
    if genai_errors is not None:
        if isinstance(exc, genai_errors.ClientError):
            http_code  = getattr(exc, "code", 0)
            status_str = str(getattr(exc, "status", "") or "").upper()
            return http_code == 429 or "RESOURCE_EXHAUSTED" in status_str
    return False


def _classify_error(exc: Exception, request_id: str) -> AgentError:
    """Map any provider exception → user-facing AgentError."""
    code = "unknown"

    if isinstance(exc, httpx.HTTPStatusError):
        s = exc.response.status_code
        if s == 400:
            code = "invalid_request"
        elif s in (401, 403):
            code = "auth_failure"
        elif s in (500, 502, 503, 529):
            code = "service_unavailable"

    elif genai_errors is not None:
        if isinstance(exc, genai_errors.ClientError):
            http_code  = getattr(exc, "code", 0)
            status_str = str(getattr(exc, "status", "") or "").upper()
            if http_code == 429:
                code = (
                    "quota_exhausted"
                    if "RESOURCE_EXHAUSTED" in status_str or "QUOTA" in status_str
                    else "rate_limited"
                )
            elif http_code in (401, 403):
                code = "auth_failure"
            elif http_code == 400:
                code = "invalid_request"
        elif isinstance(exc, genai_errors.ServerError):
            code = "service_unavailable"

    return AgentError(
        code=code,
        user_message=USER_MESSAGES[code],
        retry_advice=RETRY_ADVICE[code],
        request_id=request_id,
    )


# ── Board context builder ──────────────────────────────────────────────────────

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
        "source": _resolve_endpoint(
            c.source_step_id, c.source_element_id, step_map, element_map
        ),
        "target": _resolve_endpoint(
            c.target_step_id, c.target_element_id, step_map, element_map
        ),
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
    if len(connectors) <= _CONNECTOR_FULL_LIMIT:
        return {
            "connectors": [
                _serialize_connector(c, step_map, element_map) for c in connectors
            ]
        }

    by_type: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    connected_ids: set[str] = set()
    target_ids:    set[str] = set()
    source_ids:    set[str] = set()

    for c in connectors:
        by_type[c.connector_type] = by_type.get(c.connector_type, 0) + 1
        by_tier[c.tier]           = by_tier.get(c.tier, 0) + 1
        for fld in (
            c.source_element_id, c.target_element_id,
            c.source_step_id,    c.target_step_id,
        ):
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
            "total":             len(connectors),
            "by_type":           by_type,
            "by_tier":           by_tier,
            "orphaned_elements": orphaned,
            "dead_ends":         dead_ends,
        },
        "connectors_sample": [
            _serialize_connector(c, step_map, element_map)
            for c in connectors[-20:]
        ],
    }


async def build_board_context(db: AsyncSession, board_id: str) -> dict:
    board_res = await db.execute(select(Board).where(Board.id == board_id))
    board = board_res.scalar_one_or_none()
    if not board:
        return {}

    caps_res = await db.execute(
        select(Capability)
        .where(Capability.board_id == board_id)
        .order_by(Capability.cap_id)
    )
    caps = caps_res.scalars().all()

    elems_res = await db.execute(
        select(Element)
        .where(Element.board_id == board_id)
        .order_by(Element.updated_at.desc())
    )
    all_elements = elems_res.scalars().all()

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

    connector_ctx = _build_connector_context(
        connectors, all_elements, step_map, element_map
    )

    return {
        "board_id":      board.id,
        "title":         board.title,
        "domain":        board.domain,
        "current_phase": board.phase,
        "version":       board.version,
        "board_state":   board.state,
        "canvas_summary": {
            "placed_element_count":   len(placed_elements),
            "orphaned_element_count": len(orphaned_elements),
            "swimlane_count":         len((board.state or {}).get("swimlanes", [])),
            "step_count":             len((board.state or {}).get("steps", [])),
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
        "unplaced_elements": [
            {"id": str(e.id), "type": e.type, "name": e.name}
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


# ── System prompt builder ──────────────────────────────────────────────────────

def _has_ai_content(ctx: dict) -> bool:
    if ctx.get("capabilities"):
        return True
    return any(e.get("type") == "ai_capability" for e in ctx.get("elements", []))


def _placement_reference(ctx: dict) -> str:
    state     = ctx.get("board_state") or {}
    swimlanes = state.get("swimlanes", [])
    steps     = state.get("steps", [])
    if not swimlanes and not steps:
        return ""
    lines = [
        "",
        "## PLACEMENT REFERENCE — copy these IDs verbatim when proposing "
        "create_element actions. Do NOT invent, modify, or guess IDs.",
        "",
    ]
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
    ctx_json      = json.dumps(ctx, indent=2, default=str)
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
- Reference real IDs from the board context for ALL other actions. NEVER use a name as an ID.
- Reference real connector IDs from the connectors list when proposing update_connector or delete_connector.
- For create_connector: use real element or step IDs from the board context as source/target.
- Each action is independent — the user can approve some and reject others.
- Do not propose more than 5 connector actions in a single response — prioritise the most impactful gaps."""


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
    return f"Role context: {text}" if text else ""


def _connectors_section(ctx: dict) -> str:
    if "connectors_summary" in ctx:
        s              = ctx["connectors_summary"]
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
            "If asked about flows or relationships, acknowledge that no connectors "
            "have been drawn and invite the user to add them."
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
- Only reference connectors that exist in the provided context. Never invent connections.
- Identify orphaned elements (zero connectors) — they may be incomplete or not yet wired in.
- Identify missing failure paths: steps or elements with no 'failure' connector out.
- Flag data flows that cross visibility lines (frontstage → backstage).
- Note bottlenecks: elements with many incoming 'dependency' connectors.

When proposing connector changes:
- Propose create_connector when a high-stakes step has no failure path, or a flow is implied but not drawn.
- Propose update_connector when a connector is mis-typed or has a misleading label.
- Propose delete_connector when a connector is redundant.
- Always include a rationale field.
- Never propose more than 5 connector actions per response.\
"""


def build_system_prompt(ctx: dict, role: Optional[str] = None) -> str:
    sections = [_core_section(ctx)]
    sections.append(_connectors_section(ctx))
    if _has_ai_content(ctx):
        sections.append(_hcai_section())
    if role:
        s = _role_section(role)
        if s:
            sections.append(s)
    sections.append(_ACTIONS_SECTION)
    return "\n\n".join(sections)


# ── Context compaction (for small-context providers like Cerebras 8 K) ─────────

def _compact_ctx(ctx: dict) -> dict:
    """Minimal board context — strips full board_state JSON and connector details."""
    return {
        "board_id":      ctx.get("board_id"),
        "title":         ctx.get("title"),
        "domain":        ctx.get("domain"),
        "current_phase": ctx.get("current_phase"),
        "canvas_summary": ctx.get("canvas_summary", {}),
        "capabilities":  ctx.get("capabilities", [])[:5],
        "elements":      ctx.get("elements", [])[:8],
        "open_insights": ctx.get("open_insights", [])[:3],
    }


def _compact_system_prompt(ctx: dict, role: Optional[str] = None) -> str:
    """Condensed system prompt for providers with small context windows.
    Drops full board_state JSON, connector details, and HCAI section."""
    sections = [_core_section(_compact_ctx(ctx))]
    if role:
        s = _role_section(role)
        if s:
            sections.append(s)
    sections.append(_ACTIONS_SECTION)
    return "\n\n".join(sections)


def _trim_history(
    history: list[dict],
    system_prompt: str,
    current_message: str,
    context_chars: int,
) -> tuple[list[dict], bool]:
    """Trim history so that total chars fit within 75 % of context_chars.
    Returns (trimmed_history, was_compacted)."""
    budget = int(context_chars * 0.75)

    for keep in (20, 8, 4, 2, 0):
        trimmed = history[-keep:] if keep > 0 else []
        total   = (
            len(system_prompt) + len(current_message)
            + sum(len(str(m.get("content", ""))) for m in trimmed)
        )
        if total <= budget:
            return trimmed, keep < len(history)

    return [], True


# ── OpenAI-compatible call (Groq / Cerebras) ──────────────────────────────────

def _history_to_openai(history: list[dict]) -> list[dict]:
    return [
        {
            "role":    m["role"],
            "content": m["content"] if isinstance(m["content"], str) else str(m["content"]),
        }
        for m in history
    ]


async def _call_openai_compat(
    provider:      dict,
    api_key:       str,
    system_prompt: str,
    history:       list[dict],
    message:       str,
) -> tuple[str, int]:
    """POST to an OpenAI-compatible /chat/completions endpoint.
    Returns (response_text, total_tokens).
    Raises httpx.HTTPStatusError on any HTTP error (including 429)."""
    messages = [{"role": "system", "content": system_prompt}]
    messages += _history_to_openai(history)
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            provider["url"],
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       provider["model"],
                "messages":    messages,
                "max_tokens":  MAX_RESPONSE_TOKENS,
                "temperature": 0.7,
            },
        )
        resp.raise_for_status()

    data   = resp.json()
    text   = data["choices"][0]["message"]["content"] or ""
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return text, tokens


# ── Gemini SDK call (supports inline file attachments) ────────────────────────

def _history_to_gemini(history: list[dict]) -> list:
    if types is None:
        return []
    return [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(
                text=m["content"] if isinstance(m["content"], str) else str(m["content"])
            )],
        )
        for m in history
    ]


async def _build_user_parts(
    db: AsyncSession,
    attachment_ids: list[str],
    board_id: str,
    text: str,
) -> tuple[list, list[dict]]:
    from app.services.upload_service import download_bytes

    parts:       list       = []
    attach_refs: list[dict] = []

    if attachment_ids:
        uploads_res = await db.execute(
            select(Upload).where(
                Upload.id.in_(attachment_ids),
                Upload.board_id == board_id,
            )
        )
        for up in uploads_res.scalars().all():
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


async def _call_gemini(
    system_prompt: str,
    history:       list[dict],
    user_parts:    list,
) -> tuple[str, int]:
    client   = _get_gemini_client()
    contents = _history_to_gemini(history) + [
        types.Content(role="user", parts=user_parts)
    ]
    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=MAX_RESPONSE_TOKENS,
        ),
    )
    text   = response.text or ""
    tokens = (
        response.usage_metadata.total_token_count
        if response.usage_metadata else 0
    )
    # Surface truncation to the user
    try:
        reason = response.candidates[0].finish_reason if response.candidates else None
        if reason and str(reason).upper() in ("MAX_TOKENS", "2"):
            text = (
                text.rstrip()
                + "\n\n*Response reached length limit. "
                  "Ask me to continue, or narrow your question.*"
            )
    except Exception:
        pass
    return text, tokens


# ── Structured response parser ─────────────────────────────────────────────────

def _parse_agent_response(text: str) -> tuple[str, list[dict]]:
    """Try to parse {"message": ..., "actions": [...]} from the response.
    Falls back to (text, []) if the response is plain prose."""
    import re

    def _extract(data: dict) -> tuple[str, list[dict]] | None:
        if isinstance(data, dict) and isinstance(data.get("message"), str):
            actions = data.get("actions", [])
            if isinstance(actions, list):
                valid = [
                    a for a in actions
                    if isinstance(a, dict)
                    and isinstance(a.get("type"), str)
                    and isinstance(a.get("payload"), dict)
                ]
                return data["message"], valid
        return None

    stripped = text.strip()

    if stripped.startswith("{"):
        try:
            result = _extract(json.loads(stripped))
            if result:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    m = re.search(r"```(?:json)?\s*(\{.*?})\s*```", stripped, re.DOTALL)
    if m:
        try:
            result = _extract(json.loads(m.group(1)))
            if result:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    match = re.search(r'\{\s*"message"\s*:', stripped)
    if match:
        try:
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(stripped, match.start())
            result  = _extract(data)
            if result:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return text, []


# ── Main chat function ─────────────────────────────────────────────────────────

async def chat(
    db:             AsyncSession,
    board_id:       str,
    user_id:        str,
    message:        str,
    history:        list[dict],
    role:           Optional[str] = None,
    attachment_ids: list[str]     = [],
) -> tuple[str, int, str, list[dict]]:
    """
    Call the AI with board-aware context, auto-failing over across providers.

    Provider order: Groq → Cerebras → Gemini
    - On HTTP 429 from any provider: silently try the next.
    - If all return 429: raise AgentCallError(code="all_providers_exhausted").
    - Requests with attachments go directly to Gemini (only provider that
      supports inline file data).
    - History is automatically compacted when routing to Cerebras (8 K context).

    Returns (display_text, total_tokens, assistant_message_id, actions).
    Raises AgentCallError on any non-rate-limit AI failure.
    """
    global _consecutive_failures, _last_error_code

    request_id = str(uuid.uuid4())

    # Build board context and full system prompt once (reused across providers).
    ctx         = await build_board_context(db, board_id)
    full_system = build_system_prompt(ctx, role=role)
    trimmed     = history[-MAX_HISTORY_MESSAGES:]

    # Attachments require Gemini (inline file data).
    # If types is None (SDK not installed) skip Gemini from the non-attach chain.
    if attachment_ids:
        if types is None:
            raise HTTPException(
                503, "Attachment support requires google-genai to be installed."
            )
        user_parts, attach_refs = await _build_user_parts(
            db, attachment_ids, board_id, message
        )
        providers_to_try = [p for p in _PROVIDERS if p["name"] == "gemini"]
    else:
        user_parts   = [types.Part(text=message)] if types is not None else []
        attach_refs  = []
        providers_to_try = [
            p for p in _PROVIDERS
            if not (p["name"] == "gemini" and genai is None)
        ]

    # Persist user message BEFORE the LLM call so it survives AI errors.
    user_msg = ChatMessage(
        board_id=board_id, user_id=user_id, role="user",
        content=message, attachments=attach_refs,
    )
    db.add(user_msg)
    await db.commit()

    # ── Provider rotation loop ──────────────────────────────────────────────
    last_exc: Optional[Exception] = None
    provider_used = "unknown"
    text = ""
    tokens = 0

    for provider in providers_to_try:
        api_key = _provider_key(provider["name"])
        if not api_key:
            log.debug("Skipping provider %s — API key not configured.", provider["name"])
            continue

        try:
            if provider["name"] == "gemini":
                # Gemini SDK path — supports attachments, large context.
                text, tokens = await _call_gemini(full_system, trimmed, user_parts)

            else:
                # OpenAI-compat path (Groq / Cerebras).
                system = (
                    _compact_system_prompt(ctx, role)
                    if provider["compact"]
                    else full_system
                )
                hist, was_compacted = _trim_history(
                    trimmed, system, message, provider["context_chars"]
                )
                # Prepend a condensation note so the model has orientation.
                effective_msg = message
                if was_compacted:
                    effective_msg = (
                        f"[Context note: earlier messages were omitted to fit "
                        f"this provider's context window. Board: "
                        f"\"{ctx.get('title', 'untitled')}\" "
                        f"({ctx.get('domain', 'unknown')} domain).]\n\n"
                        + message
                    )
                text, tokens = await _call_openai_compat(
                    provider, api_key, system, hist, effective_msg
                )

            provider_used = provider["name"]
            break  # success — exit the loop

        except Exception as exc:
            if _is_rate_limit(exc):
                log.warning(
                    "Provider %s rate-limited (request_id=%s) — trying next.",
                    provider["name"], request_id,
                )
                last_exc = exc
                continue  # try next provider

            # Non-rate-limit error: classify and surface immediately.
            _consecutive_failures += 1
            agent_error = _classify_error(exc, request_id)
            _last_error_code = agent_error.code
            log.error(
                "AI error (provider=%s request_id=%s code=%s): %s: %s",
                provider["name"], request_id, agent_error.code,
                type(exc).__name__, exc,
            )
            raise AgentCallError(error=agent_error) from exc

    else:
        # Loop completed without break — every provider returned 429.
        _consecutive_failures += 1
        _last_error_code = "all_providers_exhausted"
        log.warning(
            "All AI providers rate-limited (request_id=%s). "
            "Groq/Cerebras/Gemini daily limits exhausted.",
            request_id,
        )
        raise AgentCallError(
            error=AgentError(
                code="all_providers_exhausted",
                user_message=USER_MESSAGES["all_providers_exhausted"],
                retry_advice=RETRY_ADVICE["all_providers_exhausted"],
                request_id=request_id,
            )
        ) from last_exc

    # ── Success path ────────────────────────────────────────────────────────
    _consecutive_failures = 0
    _last_error_code      = None

    log.info(
        "Chat tokens: %d (board=%s provider=%s attachments=%d)",
        tokens, board_id, provider_used, len(attach_refs),
    )

    display_text, actions = _parse_agent_response(text)

    asst_msg = ChatMessage(
        board_id=board_id, user_id=None, role="assistant",
        content=text, token_count=tokens,
    )
    db.add(asst_msg)
    await db.flush()

    return display_text, tokens, str(asst_msg.id), actions
