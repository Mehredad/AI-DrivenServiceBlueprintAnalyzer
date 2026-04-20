"""
Blueprint AI — FastAPI application (Vercel serverless edition).

Key differences from a traditional deployment:
- No uvicorn (Vercel runs ASGI directly)
- No StaticFiles mount (frontend is served by Vercel's CDN separately)
- No persistent connection pool (each invocation is stateless)
- Lifespan only runs DB connectivity check — no pool warmup
- Docs disabled in production (reduce attack surface)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import get_settings
from app.database import AsyncSessionLocal

from app.routers.auth         import router as auth_router
from app.routers.boards       import router as boards_router
from app.routers.capabilities import router as caps_router
from app.routers.agent        import router as agent_router
from app.routers.insights     import router as insights_router
from app.routers.governance   import router as governance_router
from app.routers.exports      import router as exports_router
from app.routers.audit        import router as audit_router

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
log = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lightweight startup check — no pool warmup (serverless is stateless)
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        log.info("DB connection OK")
    except Exception as exc:
        log.warning(f"DB connection check failed: {exc}")
    yield
    # No teardown needed — Vercel recycles the process


app = FastAPI(
    title="Blueprint AI API",
    version="1.0.0",
    description="Human-Centred AI Service Design Tool",
    # Hide docs in production — Vercel deployments are public
    docs_url    ="/docs"         if not settings.is_production else None,
    redoc_url   ="/redoc"        if not settings.is_production else None,
    openapi_url ="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow frontend Vercel domain + localhost in dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"]          = "1; mode=block"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# All routers
app.include_router(auth_router)
app.include_router(boards_router)
app.include_router(caps_router)
app.include_router(agent_router)
app.include_router(insights_router)
app.include_router(governance_router)
app.include_router(exports_router)
app.include_router(audit_router)


@app.get("/health", tags=["health"])
async def health():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status":      "ok" if db_ok else "degraded",
            "database":    "ok" if db_ok else "unreachable",
            "version":     "1.0.0",
            "environment": settings.environment,
        },
    )
