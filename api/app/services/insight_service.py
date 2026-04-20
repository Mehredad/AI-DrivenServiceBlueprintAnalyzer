"""
Insight service — uses the Anthropic API to analyse the live board state
and return structured insights that get persisted to the insights table.
"""
import json
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Insight
from app.services.agent_service import build_board_context

settings = get_settings()
_client  = AsyncAnthropic(api_key=settings.anthropic_api_key)

INSIGHT_PROMPT = """\
Analyse this HCAI blueprint board and return a JSON array of insights.

Each insight object must have EXACTLY these fields:
- "severity":    one of "high" | "medium" | "low" | "info" | "positive"
- "title":       concise string, max 80 characters
- "description": 1-3 sentence explanation, max 300 characters
- "source_ref":  where the issue comes from (e.g. "Step 3 · AI swimlane · CAP-001")
- "actions":     array of objects, each with "label" (string) and "action_type" (string)

Rules:
- Include at most 8 insights total
- Prioritise real issues over generic ones — reference specific steps, swimlanes, cap IDs
- Always include at least one "positive" insight if something is done well
- Always flag missing XAI strategies, undocumented overrides, transparency gaps, bias risks
- Return ONLY the raw JSON array — no markdown fences, no preamble, no explanation

Example action_types: "add_element", "flag_risk", "escalate_governance", "open_monitoring", "ask_agent"
"""


async def generate_insights(db: AsyncSession, board_id: str, user_id: str) -> list[Insight]:
    """
    Ask the AI to analyse the board and persist the resulting insights.
    Returns the list of newly created Insight objects.
    """
    ctx = await build_board_context(db, board_id)
    ctx_str = json.dumps(ctx, indent=2, default=str)

    response = await _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=(
            "You are an HCAI design expert analysing a service blueprint board. "
            "You always respond with valid JSON only — no prose, no markdown."
        ),
        messages=[
            {"role": "user", "content": f"Board state:\n{ctx_str}\n\n{INSIGHT_PROMPT}"}
        ],
    )

    raw = response.content[0].text.strip()
    # Strip accidental markdown fences if the model adds them
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        items: list[dict] = json.loads(raw)
        if not isinstance(items, list):
            items = []
    except json.JSONDecodeError:
        items = []

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
