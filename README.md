# Blueprint AI

**Human-Centred AI Service Design Tool** — a collaborative web application for designing, governing, and improving AI-powered services using the Understand → Harvest → Improve framework.

Built on the research of [Atariani & Ajala (2026) — AI-Driven Service Blueprints](https://github.com/Mehredad/AI-DrivenServiceBlueprintAnalyzer).

---

## Stack

| Layer | Technology | Hosting |
|---|---|---|
| Frontend | Vanilla HTML/CSS/JS | Vercel (CDN) |
| API | FastAPI (Python 3.12) | Vercel serverless |
| Database | PostgreSQL | Supabase (free tier) |
| Realtime | Supabase Realtime | Supabase |
| AI agent | Anthropic claude-sonnet | Server-side proxy |
| Auth | JWT + bcrypt | Self-contained |

---

## Features

- **Service blueprint canvas** — swimlane editor with 6 lanes (Patient, Staff, AI System, Doctor, Governance, Data Flow)
- **AI capability register** — structured CRUD for AI capabilities with XAI strategy, autonomy level, and harm checks
- **AI agent** — board-aware collaborator powered by Claude, proxied server-side (API key never exposed)
- **Proactive insights** — AI analyses the board and surfaces risks, gaps, and positive observations
- **Real-time collaboration** — multiple users edit the same board simultaneously via Supabase Realtime
- **Governance tracking** — decisions, audit log, oversight checkpoints
- **Export** — PDF and JSON board exports
- **Onboarding** — role-aware AI guide for designers, clinicians, data scientists, and governance officers

---

## Local Development

### Prerequisites
- Python 3.12+
- A [Supabase](https://supabase.com) project (free tier)
- An [Anthropic API key](https://console.anthropic.com)

### 1. Clone and install

```bash
git clone https://github.com/Mehredad/AI-DrivenServiceBlueprintAnalyzer.git
cd AI-DrivenServiceBlueprintAnalyzer
pip install -r requirements.txt
pip install aiosqlite   # for local SQLite testing only
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY,
# SECRET_KEY, ANTHROPIC_API_KEY, ALLOWED_ORIGINS
```

**Generate a secure SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

### 3. Run database migrations

```bash
cd api
alembic upgrade head
cd ..
```

### 4. Start the development server

```bash
cd api
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

Open `frontend/index.html` in your browser (or serve it with any static server).

---

## Deployment

### Supabase setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **Settings → Database → Connection string** — copy the **Transaction pooler URI** (port 6543)
3. Go to **Settings → API** — copy `SUPABASE_URL` and the `service_role` key
4. Run the initial migration against your Supabase DB:
   ```bash
   DATABASE_URL="postgresql+asyncpg://..." alembic upgrade head
   ```

### Vercel deployment

1. Install the [Vercel CLI](https://vercel.com/cli): `npm i -g vercel`
2. Link your repo:
   ```bash
   vercel link
   ```
3. Add environment variables in **Vercel Dashboard → Project → Settings → Environment Variables**:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Supabase Transaction pooler URI (asyncpg) |
   | `SUPABASE_URL` | Your Supabase project URL |
   | `SUPABASE_SERVICE_KEY` | Supabase service_role key |
   | `SECRET_KEY` | 64-char random hex |
   | `ANTHROPIC_API_KEY` | Your Anthropic key |
   | `ALLOWED_ORIGINS` | `https://your-app.vercel.app` |
   | `ENVIRONMENT` | `production` |

4. Deploy:
   ```bash
   vercel --prod
   ```

### CI/CD (GitHub Actions)

Add these secrets to your GitHub repository (**Settings → Secrets → Actions**):

| Secret | Where to find |
|---|---|
| `VERCEL_TOKEN` | Vercel Dashboard → Settings → Tokens |
| `VERCEL_ORG_ID` | `vercel link` output or `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | `vercel link` output or `.vercel/project.json` |

Every push to `main` will: run tests → deploy to Vercel automatically.

---

## Running Tests

```bash
pip install aiosqlite pytest-asyncio
pytest tests/ -v
```

Tests use SQLite (no Postgres needed). The CI pipeline runs tests before every deploy.

---

## API Reference

Once deployed, the full interactive API docs are available at `/docs` in development mode.

| Endpoint group | Base path |
|---|---|
| Auth | `/api/auth/` |
| Boards | `/api/boards/` |
| Capabilities | `/api/boards/{id}/capabilities/` |
| AI Agent | `/api/agent/` |
| Insights | `/api/boards/{id}/insights/` |
| Governance | `/api/boards/{id}/governance/` |
| Exports | `/api/boards/{id}/export/` |
| Audit | `/api/boards/{id}/audit/` |
| Health | `/health` |

---

## Project Structure

```
AI-DrivenServiceBlueprintAnalyzer/
├── api/                        ← FastAPI backend (Vercel serverless entry)
│   ├── index.py                ← Vercel ASGI entry point
│   ├── alembic/                ← Database migrations
│   └── app/
│       ├── main.py             ← App assembly (CORS, routers, health)
│       ├── config.py           ← Environment variable settings
│       ├── database.py         ← Async SQLAlchemy engine
│       ├── models.py           ← All ORM models
│       ├── schemas.py          ← All Pydantic schemas
│       ├── routers/            ← Route handlers (one file per domain)
│       ├── services/           ← Business logic (auth, boards, agent, exports)
│       └── middleware/         ← JWT auth dependency
├── frontend/
│   └── index.html              ← Complete single-file frontend
├── tests/                      ← pytest test suite
├── requirements.txt            ← Python dependencies (Vercel reads this)
├── vercel.json                 ← Vercel routing configuration
├── .env.example                ← Environment variable template
├── .github/workflows/
│   └── deploy.yml              ← CI/CD: test → deploy on push to main
└── ARCHITECTURE.md             ← Full architectural decisions and build plan
```

---

## Security

- JWT access tokens (15 min) + rotating refresh tokens (7 days)
- Passwords hashed with bcrypt (12 rounds)
- Anthropic API key stored server-side only — never sent to the browser
- Rate limiting: 200 req/min general, stricter on auth endpoints
- CORS restricted to declared frontend origins
- Security headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, HSTS in production
- Audit log is INSERT-only — all board changes are immutably recorded

---

## Citation

If using this tool in academic or research contexts, please cite:

> Atariani, M., & Ajala, O. (2026). *AI Driven Service Blueprints As a New Methodological Tool for HCAI Experience Design*. Proceedings of CHI 2026 Workshop. ACM.

> Atariani, M. (2024). *A Capability Centric Framework for Delivering Human Centred AI Services in Healthcare*. Independent Research.

> Mehredad (2024). *AI-Driven Service Blueprint Analyzer*. GitHub. https://github.com/Mehredad/AI-DrivenServiceBlueprintAnalyzer

---

## License

MIT — free to use, modify, and distribute with attribution.
