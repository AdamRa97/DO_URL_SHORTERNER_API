from fastapi import APIRouter

from app.api.v1 import analytics, health, links, tokens, users

router = APIRouter()

router.include_router(health.router)
router.include_router(tokens.router)
router.include_router(users.router)
router.include_router(links.router)
router.include_router(analytics.router)
