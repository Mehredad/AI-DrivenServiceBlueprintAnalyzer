"""
Insight service — analyses the live board state and returns structured insights.
Tries NVIDIA NIM first (free tier) and falls back to Google Gemini if NIM is
unavailable or fails.
"""
import json
import logging

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Insight
from app.services.agent_service import build_board_context
from app.services.nim_client import nim_complete

log = logging.getLogger(__name__)
settings = get_settings()
_gemini: genai.Client | None = None


def _get_gemini() -> genai.Client:
    global _gemini
    if _gemini is None:
        _gemini = genai.Client(api_key=settings.gemini_api_key)
    return _gemini


_SYSTEM = (
    "You are an expert service-design analyst reviewing a system journey map. "
    "You always respond with valid JSON only — no prose, no markdown fences."
)

_PROMPT = """\
Analyse this blueprint board and return a JSON array of insights.

Each insight object must have EXACTLY these fields:
- "severity":    one of "high" | "medium" | "low" | "info" | "positive"
- "title":       concise string, max 80 characters
- "description": 1-3 sentence explanation, max 300 characters
- "source_ref":  where the issue comes from (e.g. "Step 3 · AI swimlane · CAP-001")
- "actions":     array of objects, each with "label" (string) and "action_type" (string)

Rules:
- Include at most 8 insights total
- Prioritise real issues — reference specific steps, swimlane names, element IDs
- Always include at least one "positive" insight if something is done well
- Flag missing XAI strategies, undocumented overrides, transparency gaps, bias risks only when AI capabilities are present on the board
- If the board has no elements, return a single info insight encouraging the user to start mapping
- Return ONLY the raw JSON array — no markdown fences, no preamble

Example action_types: "add_element", "flag_risk", "escalate_governance", "open_monitoring", "ask_agent"
"""


def _parse_insights(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        items = json.loads(text)
        return items if isinstance(items, list) else []
    except json.JSONDecodeError:
        log.warning("Failed to parse insight JSON: %s", text[:200])
        return []


async def generate_insights(db: AsyncSession, board_id: str, user_id: str) -> list[Insight]:
    """
    Ask the AI to analyse the board and persist the resulting insights.
    Tries NIM first (free); falls back to Gemini.
    Returns the list of newly created Insight objects.
    """
    ctx = await build_board_context(db, board_id)
    ctx_str = json.dumps(ctx, indent=2, default=str)
    user_msg = f"Board state:\n{ctx_str}\n\n{_PROMPT}"

    raw = await nim_complete(system=_SYSTEM, user=user_msg, max_tokens=2048)

    if raw is None:
        log.info("NIM unavailable for insights — using Gemini")
        response = await _get_gemini().aio.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Content(role="user", parts=[types.Part(text=user_msg)])],
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                max_output_tokens=2048,
            ),
        )
        raw = response.text or ""

    items = _parse_insights(raw)

    created: list[Insight] = []
    for item in items[:8]:
        ins = Insight(
            board_id=board_id,
            severity=item.get("severity", "info"),
            title=str(item.get("title", ""))[:500],
            description=item.get("description"),
            source_ref=item.get("source_ref"),
            actions=item.get("actions", []),
        )
        db.add(ins)
        created.append(ins)

    await db.flush()
    return created
