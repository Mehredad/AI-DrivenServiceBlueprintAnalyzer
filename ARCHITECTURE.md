# Blueprint AI — Architecture & Build Plan
# LOCKED v2.0 — Updated after Vercel/Supabase/Render decision

## ── FINAL DECISIONS (do not re-ask) ──────────────────────────────────────────
# Frontend hosting:   Vercel (static HTML — blueprint-ai-v4.html → index.html)
# Backend API:        FastAPI on Render free tier (always-on, no cold starts)
# Database:           Supabase managed PostgreSQL (free tier, 500MB)
# Real-time collab:   Supabase Realtime (WebSocket channels, replaces custom WS)
# Auth:               FastAPI JWT (bcrypt + python-jose) — Supabase Auth NOT used
#                     (we control auth to keep the API self-contained)
# AI:                 Anthropic API server-side, single key, proxied via FastAPI
# Storage:            PostgreSQL JSONB for board state, BYTEA for exports
# Export:             PDF (WeasyPrint) + JSON — served as file download
# CI/CD:              GitHub Actions → Render auto-deploy on push to main
# Env secrets:        Render environment variables (never in code)
#
# WHY THIS STACK:
# - Vercel free: frontend static hosting, CDN, custom domain, HTTPS — zero cost
# - Render free: 750h/month, always-on, Python native, no serverless cold starts
# - Supabase free: 500MB Postgres, Realtime channels (WebSocket), Row Level Security
# - All three free tiers together cover a 2-3 month MVP comfortably
# ──────────────────────────────────────────────────────────────────────────────

## ── REPOSITORY STRUCTURE ─────────────────────────────────────────────────────
#
# AI-DrivenServiceBlueprintAnalyzer/
# ├── .github/
# │   └── workflows/
# │       ├── deploy-backend.yml   ← test → deploy to Render on push to main
# │       └── deploy-frontend.yml  ← deploy frontend/ to Vercel
# ├── backend/
# │   ├── app/
# │   │   ├── __init__.py
# │   │   ├── main.py              ← FastAPI app, CORS, lifespan, all routers
# │   │   ├── config.py            ← pydantic-settings (reads env vars)
# │   │   ├── database.py          ← async SQLAlchemy + Supabase connection
# │   │   ├── models.py            ← all ORM models (single file for clarity)
# │   │   ├── schemas.py           ← all Pydantic schemas
# │   │   ├── routers/
# │   │   │   ├── __init__.py
# │   │   │   ├── auth.py          ← /api/auth/register|login|refresh|logout|me
# │   │   │   ├── boards.py        ← /api/boards CRUD + collaborators
# │   │   │   ├── capabilities.py  ← /api/boards/{id}/capabilities CRUD
# │   │   │   ├── agent.py         ← /api/agent/chat + chat history
# │   │   │   ├── insights.py      ← /api/boards/{id}/insights CRUD + generate
# │   │   │   ├── governance.py    ← /api/boards/{id}/governance CRUD
# │   │   │   ├── exports.py       ← /api/boards/{id}/export/pdf|json
# │   │   │   └── audit.py         ← /api/boards/{id}/audit (read-only)
# │   │   ├── services/
# │   │   │   ├── __init__.py
# │   │   │   ├── auth_service.py  ← JWT, bcrypt, refresh token logic
# │   │   │   ├── board_service.py ← board CRUD, access control, state merge
# │   │   │   ├── agent_service.py ← Anthropic API proxy, system prompt builder
# │   │   │   ├── insight_service.py ← AI-driven board analysis
# │   │   │   └── export_service.py  ← PDF + JSON generation
# │   │   └── middleware/
# │   │       ├── __init__.py
# │   │       └── auth_middleware.py ← JWT dependency for route protection
# │   ├── alembic/
# │   │   ├── env.py
# │   │   ├── script.py.mako
# │   │   └── versions/            ← migration files
# │   ├── tests/
# │   │   ├── conftest.py
# │   │   ├── test_auth.py
# │   │   ├── test_boards.py
# │   │   └── test_agent.py
# │   ├── alembic.ini
# │   ├── requirements.txt
# │   ├── Dockerfile               ← for Render deployment
# │   ├── render.yaml              ← Render service config
# │   └── .env.example
# ├── frontend/
# │   └── index.html               ← blueprint-ai-v4.html, API calls updated
# ├── vercel.json                  ← Vercel deployment config
# └── README.md
# ──────────────────────────────────────────────────────────────────────────────

## ── DATABASE SCHEMA ──────────────────────────────────────────────────────────
# (See models.py for full ORM — this is the logical schema)
#
# users, refresh_tokens, boards, board_collaborators,
# capabilities, chat_messages, insights, governance_decisions,
# audit_logs, exports
#
# Key design decisions:
# - boards.state = JSONB (entire canvas state stored as one document)
# - audit_logs = INSERT-only (application enforces, no DELETE granted to app user)
# - exports.file_data = BYTEA (no S3 needed at MVP scale)
# ──────────────────────────────────────────────────────────────────────────────

## ── API SURFACE ──────────────────────────────────────────────────────────────
# POST /api/auth/register        POST /api/auth/login
# POST /api/auth/refresh         POST /api/auth/logout
# GET  /api/auth/me
#
# GET  /api/boards               POST /api/boards
# GET  /api/boards/{id}          PATCH /api/boards/{id}
# DELETE /api/boards/{id}
# POST /api/boards/{id}/collaborators
# DELETE /api/boards/{id}/collaborators/{uid}
#
# GET/POST/PATCH/DELETE /api/boards/{id}/capabilities/{cap_id}
#
# POST /api/agent/chat
# GET  /api/agent/boards/{id}/history
# DELETE /api/agent/boards/{id}/history
#
# GET  /api/boards/{id}/insights
# POST /api/boards/{id}/insights/generate
# PATCH /api/insights/{id}
#
# GET/POST /api/boards/{id}/governance
#
# POST /api/boards/{id}/export/pdf
# POST /api/boards/{id}/export/json
#
# GET  /api/boards/{id}/audit
# GET  /health
# ──────────────────────────────────────────────────────────────────────────────

## ── REALTIME STRATEGY (Supabase Realtime) ────────────────────────────────────
# Instead of custom WebSocket server (which Vercel can't run):
# 1. Frontend subscribes to Supabase Realtime channel: `board:{board_id}`
# 2. When any user saves a board patch (PATCH /api/boards/{id}), the backend
#    calls supabase.channel.broadcast() to notify all subscribers
# 3. Frontend receives broadcast and merges the patch into local state
# 4. Presence (who is online) handled by Supabase Presence feature
# This is simpler than raw WebSockets and has better scaling characteristics
# ──────────────────────────────────────────────────────────────────────────────

## ── ENVIRONMENT VARIABLES ────────────────────────────────────────────────────
# DATABASE_URL       = postgresql+asyncpg://...@db.supabase.co:5432/postgres
# SUPABASE_URL       = https://xxxx.supabase.co
# SUPABASE_SERVICE_KEY = eyJ...  (service role key — server only)
# SECRET_KEY         = <64-char random hex>
# ANTHROPIC_API_KEY  = sk-ant-...
# ALLOWED_ORIGINS    = https://your-app.vercel.app,http://localhost:3000
# ENVIRONMENT        = production
# ──────────────────────────────────────────────────────────────────────────────

## ── BUILD ORDER ──────────────────────────────────────────────────────────────
# [1] requirements.txt, Dockerfile, render.yaml, vercel.json
# [2] config.py, database.py
# [3] models.py (all ORM models)
# [4] schemas.py (all Pydantic schemas)
# [5] services/auth_service.py
# [6] middleware/auth_middleware.py
# [7] routers/auth.py
# [8] services/board_service.py
# [9] routers/boards.py + routers/capabilities.py
# [10] services/agent_service.py
# [11] routers/agent.py
# [12] services/insight_service.py + routers/insights.py
# [13] routers/governance.py
# [14] services/export_service.py + routers/exports.py
# [15] routers/audit.py
# [16] main.py (assembles everything)
# [17] alembic setup + initial migration
# [18] tests/
# [19] frontend/index.html (update v4 with real API calls)
# [20] .github/workflows/ CI/CD
# [21] README.md with deploy instructions
# ──────────────────────────────────────────────────────────────────────────────

## ── RESUME INSTRUCTIONS ──────────────────────────────────────────────────────
# After any interruption, start next session with:
# "Continue building Blueprint AI. Architecture is locked in ARCHITECTURE.md.
#  Completed steps: [list]. Next step: [N] — [filename]."
# All architectural decisions are FINAL. Never re-ask answered questions.
# ──────────────────────────────────────────────────────────────────────────────
