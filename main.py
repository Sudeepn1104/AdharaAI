"""
main.py — AdharaAI production entry point.

Startup order:
  1. Load config from .env
  2. Configure logging
  3. Init database tables
  4. Register middleware (security, CORS)
  5. Register routers
  6. Register global exception handlers
"""

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from backend.models.database import init_db
from backend.middleware.security import SecurityMiddleware
from backend.routers import upload, analyze, documents, health

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO if settings.IS_PROD else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("adharaai")


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting AdharaAI v{settings.APP_VERSION} [{settings.APP_ENV}]")
    init_db()
    logger.info("Database initialised")
    yield
    logger.info("AdharaAI shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AdharaAI — Indian Legal Document Simplifier",
    description=(
        "AI-powered API that extracts, segments, risk-flags, and simplifies "
        "Indian legal documents (rental agreements, court notices, contracts)."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Hide docs in production (enable only for dev)
    docs_url="/docs" if not settings.IS_PROD else None,
    redoc_url="/redoc" if not settings.IS_PROD else None,
)


# ── Middleware ────────────────────────────────────────────────────────────────

# CORS — only allow listed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

# Rate limiting + security headers
app.add_middleware(SecurityMiddleware)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router,    prefix="/health",        tags=["Health"])
app.include_router(upload.router,    prefix="/api/upload",    tags=["Upload"])
app.include_router(analyze.router,   prefix="/api/analyze",   tags=["Analyze"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])


# ── Static files (serve frontend from /frontend) ──────────────────────────────

import os
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse("frontend/index.html")

    @app.get("/privacy", include_in_schema=False)
    def serve_privacy():
        return FileResponse("frontend/privacy.html")


# ── Global error handlers ─────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse(status_code=404, content={"error": "Not found.", "path": str(request.url.path)})

@app.exception_handler(405)
async def method_not_allowed(request: Request, exc):
    return JSONResponse(status_code=405, content={"error": "Method not allowed."})

@app.exception_handler(500)
async def internal_error(request: Request, exc):
    logger.error(f"500 error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Something went wrong on our end. Please try again."},
    )

@app.exception_handler(Exception)
async def catch_all(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred. Please try again."},
    )
