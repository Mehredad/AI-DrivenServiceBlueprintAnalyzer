# Blueprint AI — Claude Code Instructions

## Project Overview

Blueprint AI is a collaborative workspace for mapping end-to-end system journeys.
Stack: **FastAPI + SQLAlchemy + Supabase (PostgreSQL)** backend, **vanilla JS single-file** frontend (`frontend/index.html`), deployed on **Vercel**.

## Directory Structure

```
api/app/          FastAPI app: main.py, models.py, database.py, config.py
api/app/routers/  auth, boards, capabilities, agent, insights, governance, exports, audit
api/app/services/ agent_service.py (AI logic)
frontend/         index.html — entire frontend in one file
tests/            pytest + httpx async tests
PRD reference:    D:\AI-DrivenServiceBlueprintAnalyzer\PRD\
```

## Code Standards

- Python: type hints on all function signatures, no bare `except`
- JS: vanilla ES2020+, no build step, no frameworks — single `frontend/index.html`
- No comments unless the WHY is non-obvious
- No backwards-compat shims, no feature flags, no half-implementations
- SQL: always async via SQLAlchemy async sessions — never `.execute()` on a sync session

## Architecture Decisions

- Frontend is a **single HTML file** — do not split it. All JS, CSS, and HTML in `frontend/index.html`.
- Board state is stored as JSONB in `boards.state`. Swimlanes, steps, and elements all live inside this JSON object.
- The backend AI agent reads live board state and sends it to Anthropic. NVIDIA NIM handles cheaper/simpler AI tasks.
- `PATCH /api/boards/{id}` does **shallow merge with array-replace** on `state` keys — sending `{ state: { swimlanes: [...] } }` replaces the whole swimlanes array.

## AI Model Policy

| Task | Model |
|---|---|
| Planning, architecture decisions, code review | Claude Opus 4.7 via `/plan-eng-review`, `/plan-ceo-review`, `/review` (gstack) |
| Routine coding, file edits, bug fixes | Claude Sonnet 4.6 (default Claude Code model) |
| App-level simple AI tasks (insights, quick summaries) | NVIDIA NIM free models via `NIM_API_KEY` |
| App-level complex AI tasks (agent analysis, blueprint generation) | Anthropic Claude via `ANTHROPIC_API_KEY` |

When making architectural or scope decisions during development, use gstack planning skills before writing code.

## Commit Format

```
<type>(<scope>): <description>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Example: `feat(canvas): add swimlane add/rename/delete/reorder`

## PRD Workflow

PRDs are in `D:\AI-DrivenServiceBlueprintAnalyzer\PRD\`. Work in order (01 → 11).
Each PRD has acceptance criteria — run them before marking done.
Do not start PRD N+1 until PRD N's acceptance criteria pass.

## gstack Skills Available

Use these slash commands for specialised work:

- `/plan-eng-review` — architecture and engineering decisions (uses Opus)
- `/plan-ceo-review` — product scope and priority decisions (uses Opus)
- `/review` — pre-commit code review (security, bugs, best practices)
- `/qa` — browser-based QA against a running URL
- `/ship` — pre-PR checklist
- `/investigate` — root-cause debugging
- `/cso` — security audit (OWASP + STRIDE)
- `/office-hours` — product strategy questions

For all web browsing in Claude Code, use `/browse` from gstack — never use `mcp__claude-in-chrome__*` tools.

## Testing

```bash
cd api && pytest ../tests/ -v          # run all tests
pytest ../tests/test_auth.py -v        # run specific file
```

Tests use SQLite + httpx AsyncClient. No Postgres needed in CI.

## Environment Variables

Required in `.env` (see `.env.example`):
- `DATABASE_URL` — Supabase postgres URL
- `SECRET_KEY` — JWT signing key
- `ANTHROPIC_API_KEY` — Claude API (agent, complex AI tasks)
- `NIM_API_KEY` — NVIDIA NIM API (free tier, basic AI tasks)
- `ENVIRONMENT` — `development` | `production`

## Things Claude Must Never Do

- Do NOT split `frontend/index.html` into multiple files
- Do NOT add Webpack, Vite, or any build tooling
- Do NOT add mobile-responsive layout (desktop-first)
- Do NOT implement versioning/history, comments/threading, or Jira integrations
- Do NOT use `grep` or `find` as bash commands — use the Grep and Glob tools
- Do NOT commit `.env` files
- Do NOT use `--no-verify` on git hooks

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. The
skill has multi-step workflows, checklists, and quality gates that produce better
results than an ad-hoc answer. When in doubt, invoke the skill. A false positive is
cheaper than a false negative.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke /office-hours
- Strategy, scope, "think bigger", "what should we build" → invoke /plan-ceo-review
- Architecture, "does this design make sense" → invoke /plan-eng-review
- Design system, brand, "how should this look" → invoke /design-consultation
- Design review of a plan → invoke /plan-design-review
- Developer experience of a plan → invoke /plan-devex-review
- "Review everything", full review pipeline → invoke /autoplan
- Bugs, errors, "why is this broken", "wtf", "this doesn't work" → invoke /investigate
- Test the site, find bugs, "does this work" → invoke /qa (or /qa-only for report only)
- Code review, check the diff, "look at my changes" → invoke /review
- Visual polish, design audit, "this looks off" → invoke /design-review
- Developer experience audit, try onboarding → invoke /devex-review
- Ship, deploy, create a PR, "send it" → invoke /ship
- Merge + deploy + verify → invoke /land-and-deploy
- Configure deployment → invoke /setup-deploy
- Post-deploy monitoring → invoke /canary
- Update docs after shipping → invoke /document-release
- Weekly retro, "how'd we do" → invoke /retro
- Second opinion, codex review → invoke /codex
- Safety mode, careful mode, lock it down → invoke /careful or /guard
- Security audit, OWASP, "is this secure" → invoke /cso
- Save progress, "save my work" → invoke /context-save
- Resume, restore, "where was I" → invoke /context-restore
