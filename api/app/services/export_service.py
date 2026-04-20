"""
Export service — generates PDF (WeasyPrint) and JSON exports of a board.
Files are stored as BYTEA in the exports table (no S3 needed at MVP scale).
"""
import json
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Board, Capability, GovernanceDecision, Export


async def export_json(db: AsyncSession, board_id: str, user_id: str) -> bytes:
    board, caps, gov = await _load_data(db, board_id)
    payload = {
        "export_version": "1.0",
        "exported_at":    datetime.now(timezone.utc).isoformat(),
        "board": {
            "id":      board.id,
            "title":   board.title,
            "domain":  board.domain,
            "phase":   board.phase,
            "version": board.version,
            "state":   board.state,
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
                "notes":        c.notes,
            }
            for c in caps
        ],
        "governance_decisions": [
            {
                "decision_type": g.decision_type,
                "title":         g.title,
                "rationale":     g.rationale,
                "decided_at":    str(g.decided_at),
            }
            for g in gov
        ],
    }
    data = json.dumps(payload, indent=2, default=str).encode("utf-8")
    await _save_export(db, board_id, user_id, "json", data)
    return data


async def export_pdf(db: AsyncSession, board_id: str, user_id: str) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        raise RuntimeError(
            "PDF export requires WeasyPrint and its system dependencies (libpango, libcairo). "
            "Use JSON export on this deployment, or run locally with WeasyPrint installed."
        )

    board, caps, gov = await _load_data(db, board_id)
    html  = _build_html(board, caps, gov)
    data  = HTML(string=html).write_pdf()
    await _save_export(db, board_id, user_id, "pdf", data)
    return data


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_data(db, board_id):
    board_res = await db.execute(select(Board).where(Board.id == board_id))
    board     = board_res.scalar_one()

    caps_res  = await db.execute(
        select(Capability).where(Capability.board_id == board_id).order_by(Capability.cap_id)
    )
    caps = caps_res.scalars().all()

    gov_res = await db.execute(
        select(GovernanceDecision)
        .where(GovernanceDecision.board_id == board_id)
        .order_by(GovernanceDecision.decided_at.desc())
    )
    gov = gov_res.scalars().all()
    return board, caps, gov


async def _save_export(db, board_id, user_id, fmt, data):
    db.add(Export(
        board_id=board_id,
        user_id=user_id,
        format=fmt,
        file_size=len(data),
        file_data=data,
    ))
    await db.flush()


def _build_html(board, caps, gov) -> str:
    now    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    domain = board.domain or "—"
    phase  = board.phase  or "—"

    cap_rows = "".join(
        f"""<tr>
          <td>{c.cap_id}</td><td>{c.name}</td><td>{c.type or '—'}</td>
          <td class="risk-{(c.risk_level or 'low').lower()}">{c.risk_level or '—'}</td>
          <td>{c.xai_strategy or '—'}</td><td>{c.autonomy or '—'}</td>
          <td>{c.status}</td>
        </tr>"""
        for c in caps
    ) or "<tr><td colspan='7'>No capabilities registered</td></tr>"

    gov_rows = "".join(
        f"""<tr>
          <td>{g.decision_type}</td><td>{g.title}</td>
          <td>{(g.decided_at.strftime('%Y-%m-%d') if g.decided_at else '—')}</td>
        </tr>"""
        for g in gov
    ) or "<tr><td colspan='3'>No governance decisions recorded</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body   {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 11px; color: #1D1C18; margin: 0; padding: 40px; }}
  h1     {{ font-size: 20px; font-weight: 400; margin: 0 0 4px; letter-spacing: -0.3px; }}
  h2     {{ font-size: 11px; font-weight: 700; color: #5A5850; text-transform: uppercase;
            letter-spacing: 0.8px; margin: 28px 0 8px; border-top: 1px solid #EDEBE5; padding-top: 16px; }}
  .meta  {{ font-size: 10px; color: #9A9790; margin-bottom: 28px; font-family: monospace; }}
  table  {{ width: 100%; border-collapse: collapse; }}
  th     {{ text-align: left; padding: 6px 10px; background: #F5F3EF;
            border-bottom: 1px solid #D9D6CE; font-size: 9px;
            text-transform: uppercase; letter-spacing: 0.5px; color: #9A9790; }}
  td     {{ padding: 7px 10px; border-bottom: 1px solid #EDEBE5; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  .risk-high   {{ color: #B91C1C; font-weight: 600; }}
  .risk-medium {{ color: #A35800; font-weight: 600; }}
  .risk-low    {{ color: #0A7065; }}
  @page {{ margin: 40px; size: A4 landscape; }}
</style>
</head>
<body>
<h1>{board.title}</h1>
<div class="meta">
  Domain: {domain} &nbsp;·&nbsp; Phase: {phase} &nbsp;·&nbsp;
  Version: {board.version} &nbsp;·&nbsp; Exported: {now}
</div>

<h2>AI Capability Register</h2>
<table>
  <thead>
    <tr><th>ID</th><th>Name</th><th>Type</th><th>Risk</th>
        <th>XAI Strategy</th><th>Autonomy</th><th>Status</th></tr>
  </thead>
  <tbody>{cap_rows}</tbody>
</table>

<h2>Governance Decisions</h2>
<table>
  <thead><tr><th>Decision type</th><th>Title</th><th>Date</th></tr></thead>
  <tbody>{gov_rows}</tbody>
</table>
</body>
</html>"""
