from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from slowapi import Limiter, _rate_limit_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import FastAPI

import redis.asyncio as aioredis

from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.core.exceptions import (
    AliasConflictError,
    AliasValidationError,
    AuthenticationError,
    AuthorizationError,
    LinkNotFoundError,
    alias_conflict_handler,
    alias_validation_error_handler,
    authentication_error_handler,
    authorization_error_handler,
    link_not_found_handler,
)
from app.database import get_db
from app.logger import get_logger
from app.middleware.request_id import RequestIDMiddleware
from app.redis_client import get_redis_dep
from app.services import link_service
from app.tasks.click_tasks import record_click

logger = get_logger(__name__)

# Rate limiter — shared instance used by all routers
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)

# Redirect router — registered LAST so it never shadows /api/v1/* or /docs
_redirect_router = APIRouter(tags=["redirect"])


@_redirect_router.get("/{alias}", include_in_schema=True)
@limiter.limit(settings.RATE_LIMIT_REDIRECT)
async def redirect_alias(
    request: Request,
    alias: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_dep),
) -> RedirectResponse:
    """Redirect /{alias} → original URL (302). Records click as a background task."""
    url = await link_service.get_link_for_redirect(alias, db, redis)
    background_tasks.add_task(
        record_click.delay,
        alias=alias,
        raw_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
    )
    return RedirectResponse(url=url, status_code=302)


def create_app() -> FastAPI:
    app = FastAPI(
        title="URL Shortener API",
        version="1.0.0",
        description="A production-ready URL shortening service.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware (applied in reverse registration order on request)
    app.add_middleware(RequestIDMiddleware)

    # Rate limiter state + handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # Domain exception handlers
    app.add_exception_handler(AuthenticationError, authentication_error_handler)
    app.add_exception_handler(AuthorizationError, authorization_error_handler)
    app.add_exception_handler(LinkNotFoundError, link_not_found_handler)
    app.add_exception_handler(AliasConflictError, alias_conflict_handler)
    app.add_exception_handler(AliasValidationError, alias_validation_error_handler)

    # Routers — /api/v1 prefix FIRST, redirect catch-all LAST (critical ordering)
    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(_redirect_router)

    return app


app = create_app()
