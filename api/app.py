"""
FastAPI Application
Health checks, metrics, and admin API endpoints
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import Response

from core.config import settings
from core.logging import get_logger, setup_logging
from database.connection import check_db_connection, get_session
from database.redis_client import check_redis_connection

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)

# ── Prometheus metrics ─────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "api_requests_total", "Total API requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "api_request_latency_seconds", "API request latency"
)
ACTIVE_USERS = Gauge("bot_active_users_total", "Total active bot users")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    setup_logging()
    logger.info("FastAPI starting up")
    yield
    logger.info("FastAPI shutting down")


app = FastAPI(
    title="IT Pro Bot API",
    version=settings.APP_VERSION,
    description="Enterprise Telegram AI Bot Backend",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware ─────────────────────────────────────────────────────────────────

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.observe(duration)
    return response


# ── Auth dependency ────────────────────────────────────────────────────────────

async def require_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    if not credentials or credentials.credentials != settings.security.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


# ── Health endpoints ───────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()

    status = "healthy" if (db_ok and redis_ok) else "degraded"
    code = 200 if status == "healthy" else 503

    return JSONResponse(
        content={
            "status": status,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": {
                "database": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
        },
        status_code=code,
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Kubernetes readiness probe."""
    db_ok = await check_db_connection()
    if not db_ok:
        raise HTTPException(status_code=503, detail="Database not ready")
    return {"status": "ready"}


@app.get("/live", tags=["Health"])
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


# ── Metrics endpoint ───────────────────────────────────────────────────────────

@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Admin API ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/stats", tags=["Admin"], dependencies=[Depends(require_api_key)])
async def get_stats():
    from services.user_service import user_service
    stats = await user_service.get_stats()
    return stats


@app.get("/api/v1/users/{user_id}", tags=["Admin"], dependencies=[Depends(require_api_key)])
async def get_user(user_id: int):
    from services.user_service import user_service
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_premium": user.is_premium,
        "messages_count": user.messages_count,
        "ai_queries_count": user.ai_queries_count,
        "rating_points": user.rating_points,
    }
