"""
middleware/security.py
Adds rate limiting, security headers, and request logging.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta
import time
import logging
from config import settings

logger = logging.getLogger("adharaai")

# In-memory rate limit store: {ip: [timestamp, ...]}
_rate_store: dict = defaultdict(list)
RATE_WINDOW = 60   # seconds
RATE_LIMIT   = int(settings.RATE_LIMIT)   # requests per window


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ── 1. Rate limiting ──────────────────────────────────────────────────
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            window_start = now - RATE_WINDOW

            # Remove old timestamps
            _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]

            if len(_rate_store[ip]) >= RATE_LIMIT:
                logger.warning(f"Rate limit exceeded: {ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too many requests.",
                        "detail": f"You can make {RATE_LIMIT} requests per minute. Please wait and try again.",
                        "retry_after_seconds": RATE_WINDOW,
                    },
                    headers={"Retry-After": str(RATE_WINDOW)},
                )
            _rate_store[ip].append(now)

        # ── 2. Process request ────────────────────────────────────────────────
        start = time.time()
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled error: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "An unexpected error occurred. Please try again."},
            )
        duration = round((time.time() - start) * 1000)

        # ── 3. Security headers ───────────────────────────────────────────────
        response.headers["X-Content-Type-Options"]  = "nosniff"
        response.headers["X-Frame-Options"]          = "DENY"
        response.headers["X-XSS-Protection"]         = "1; mode=block"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["X-Response-Time"]           = f"{duration}ms"
        if settings.IS_PROD:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # ── 4. Request logging (no PII logged) ───────────────────────────────
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration}ms)"
        )
        return response
