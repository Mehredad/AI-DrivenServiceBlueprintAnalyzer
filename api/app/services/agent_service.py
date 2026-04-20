"""
Agent service — builds a board-aware system prompt from live DB state,
calls the Anthropic API server-side (key never leaves server),
persists both turns of the conversation.
"""
import json
from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Board, Capability, Insight, GovernanceDecision, ChatMessage

settings = get_settings()
_client  = AsyncAnthropic(api_key=settings.anthropic_api_key)

MAX_HISTORY_MESSAGES = 20   # how many prior turns to include in context
MAX_RESPONSE_TOKENS  = 1024


# ── Board context builder ─────────────────────────────────────────────────────

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


def build_system_prompt(ctx: dict) -> str:
    ctx_json = json.dumps(ctx, indent=2, default=str)
    return f"""You are the Blueprint Agent — an expert AI collaborator embedded in Blueprint AI, a human-centred AI (HCAI) service design tool.

You have full, real-time visibility of the current blueprint board. Here is its complete current state:

{ctx_json}

YOUR RESPONSIBILITIES:
1. ONBOARDING: When a user identifies their role, give them a specific, actionable starting point tailored to this exact board. Never give generic tips — always reference actual capabilities, steps, and risks from the board above.
2. BOARD ANALYSIS: Identify gaps, risks, and design opportunities. Always cite specific steps, swimlane names, and capability IDs (e.g. CAP-001).
3. DESIGN ASSISTANCE: Help with AI touchpoints, XAI strategies, autonomy levels, governance checkpoints, and monitoring rules. Offer concrete suggestions the team can act on immediately.
4. GOVERNANCE SUPPORT: Draft monitoring rules, risk notes, governance summaries, and policy language based on what is actually on this board.
5. HARM MITIGATION: Proactively flag fairness, transparency, accountability, and digital wellbeing concerns — even when not asked.

COMMUNICATION STYLE:
- Write as a knowledgeable collaborator and fellow stakeholder, not a help desk.
- Be specific: always name the exact step, swimlane, or capability ID.
- Be practical: give concrete, actionable suggestions.
- Be direct: if something is missing or wrong, say so plainly.
- Use **bold** for key terms. Use bullet lists for multiple items.
- Aim for 150–300 words unless a detailed plan is explicitly requested.

HCAI FRAMEWORK — the three phases this tool is built around:
- Understand: map human needs, stakeholder roles, candidate capabilities, success criteria beyond accuracy
- Harvest: translate capabilities into service touchpoints, XAI strategies, visibility decisions, autonomy levels
- Improve: define monitoring metrics, feedback loops, governance routines, escalation paths"""


# ── Main chat function ────────────────────────────────────────────────────────

async def chat(
    db:       AsyncSession,
    board_id: str,
    user_id:  str,
    message:  str,
    history:  list[dict],   # [{"role": "user"|"assistant", "content": "..."}]
) -> tuple[str, int, str]:
    """
    Call Anthropic API with board-aware system prompt.
    Persists both turns to chat_messages.
    Returns (response_text, total_tokens_used, assistant_message_id).
    """
    ctx    = await build_board_context(db, board_id)
    system = build_system_prompt(ctx)

    # Cap history to avoid token overrun, keep most recent turns
    trimmed = history[-MAX_HISTORY_MESSAGES:]
    messages = [
        *[{"role": h["role"], "content": h["content"]} for h in trimmed],
        {"role": "user", "content": message},
    ]

    response = await _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=MAX_RESPONSE_TOKENS,
        system=system,
        messages=messages,
    )

    text   = response.content[0].text
    tokens = response.usage.input_tokens + response.usage.output_tokens

    # Persist both turns
    user_msg = ChatMessage(
        board_id=board_id, user_id=user_id, role="user", content=message
    )
    asst_msg = ChatMessage(
        board_id=board_id, user_id=None, role="assistant",
        content=text, token_count=tokens,
    )
    db.add(user_msg)
    db.add(asst_msg)
    await db.flush()

    return text, tokens, str(asst_msg.id)
