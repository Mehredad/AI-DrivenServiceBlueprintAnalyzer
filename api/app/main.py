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
import pydantic
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import get_settings
from app.database import AsyncSessionLocal, _db_ready

from app.routers.auth         import router as auth_router
from app.routers.boards       import router as boards_router
from app.routers.capabilities import router as caps_router
from app.routers.elements     import router as elements_router
from app.routers.agent        import router as agent_router
from app.routers.insights     import router as insights_router
from app.routers.governance   import router as governance_router
from app.routers.exports      import router as exports_router
from app.routers.audit        import router as audit_router
from app.routers.uploads      import router as uploads_router
from app.routers.imports      import router as imports_router
from app.routers.history      import router as history_router
from app.routers.branches     import router as branches_router
from app.routers.connectors   import router as connectors_router

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
log = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _db_ready:
        log.error("DATABASE_URL is not set — all database operations will return 503.")
    else:
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
    response.headers["X-Content-Type-Options"]     = "nosniff"
    response.headers["X-Frame-Options"]             = "SAMEORIGIN"
    response.headers["Referrer-Policy"]              = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"]             = "1; mode=block"
    # Allow Google Sign-In popup to postMessage back to the opener
    response.headers["Cross-Origin-Opener-Policy"]  = "same-origin-allow-popups"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# All routers
app.include_router(auth_router)
app.include_router(boards_router)
app.include_router(caps_router)
app.include_router(elements_router)
app.include_router(agent_router)
app.include_router(insights_router)
app.include_router(governance_router)
app.include_router(exports_router)
app.include_router(audit_router)
app.include_router(uploads_router)
app.include_router(imports_router)
app.include_router(history_router)
app.include_router(branches_router)
app.include_router(connectors_router)


class _AnalyzeRequest(pydantic.BaseModel):
    content_type: str
    file_data: str  # base64-encoded file bytes


@app.post("/api/import/analyze", tags=["imports"])
async def analyze_blueprint_public(body: _AnalyzeRequest):
    """
    Auth-free blueprint extraction. Accepts base64-encoded file data, returns
    the extracted JSON structure (same shape as ImportJob.result).
    No DB writes, no storage.
    """
    import base64 as _b64
    from app.services import import_service

    ALLOWED = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
    ct = body.content_type.split(";")[0].strip()
    if ct not in ALLOWED:
        return JSONResponse({"detail": "Unsupported file type. Use PDF, PNG, JPG, or WebP."}, status_code=415)

    try:
        data = _b64.b64decode(body.file_data)
    except Exception:
        return JSONResponse({"detail": "Invalid file data."}, status_code=400)

    if len(data) > 10 * 1024 * 1024:
        return JSONResponse({"detail": "File too large — maximum 10 MB."}, status_code=413)

    result, _ = await import_service._run_extraction(data, ct)
    if result is None:
        return JSONResponse(
            {"detail": "Could not extract a blueprint from this file. Try a clearer image or a higher-quality PDF."},
            status_code=422,
        )
    return JSONResponse(result)


_FRONTEND = Path(__file__).parent.parent.parent / "frontend" / "index.html"
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "frontend" / "templates"


@app.get("/", include_in_schema=False)
async def serve_frontend():
    if _FRONTEND.exists():
        return FileResponse(str(_FRONTEND))
    return JSONResponse({"detail": "Frontend not found"}, status_code=404)


@app.get("/templates/{filename}", include_in_schema=False)
async def serve_template(filename: str):
    path = _TEMPLATES_DIR / filename
    if path.exists() and path.suffix == ".json":
        return FileResponse(str(path), media_type="application/json")
    return JSONResponse({"detail": "Template not found"}, status_code=404)


@app.get("/health/agent", tags=["health"])
async def health_agent():
    from app.services.agent_service import get_health_state
    return JSONResponse(status_code=200, content=get_health_state())


@app.get("/health", tags=["health"])
async def health():
    if not _db_ready:
        return JSONResponse(status_code=503, content={
            "status": "degraded", "database": "not_configured",
            "version": "1.0.0", "environment": settings.environment,
        })
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
