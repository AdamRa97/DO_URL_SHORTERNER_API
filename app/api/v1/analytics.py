from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_owner_or_admin
from app.database import get_db
from app.models.link import Link
from app.models.user import User
from app.schemas.link import StatsOut
from app.services import analytics_service

router = APIRouter(tags=["analytics"])


@router.get("/links/{alias}/stats", response_model=StatsOut)
async def get_stats(
    link_and_user: tuple[Link, User] = Depends(require_owner_or_admin),
    db: AsyncSession = Depends(get_db),
) -> StatsOut:
    """Get click statistics for a short link."""
    link, _ = link_and_user
    stats = await analytics_service.get_stats(db, link.id)
    return StatsOut(alias=link.alias, **stats)
