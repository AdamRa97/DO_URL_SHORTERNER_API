from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.api.deps import get_current_user, require_owner_or_admin
from app.config import settings
from app.database import get_db
from app.models.link import Link
from app.models.user import RoleEnum, User
from app.redis_client import get_redis_dep
from app.schemas.link import LinkCreate, LinkList, LinkOut, LinkUpdate
from app.services import link_service

router = APIRouter(tags=["links"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/links", response_model=LinkOut, status_code=201)
@limiter.limit(settings.RATE_LIMIT_LINKS_CREATE)
async def create_link(
    request: Request,
    body: LinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LinkOut:
    """Create a new shortened URL."""
    link = await link_service.create_link(
        db=db,
        owner_id=current_user.id,
        original_url=str(body.original_url),
        custom_alias=body.custom_alias,
        expires_at=body.expires_at,
    )
    return LinkOut.model_validate(link)


@router.get("/links", response_model=LinkList)
async def list_links(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LinkList:
    """List links. Admins see all links; regular users see only their own."""
    owner_id = None if current_user.role == RoleEnum.admin else current_user.id
    links, total = await link_service.list_links(db, owner_id, offset, limit)
    return LinkList(
        items=[LinkOut.model_validate(link) for link in links],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/links/{alias}", response_model=LinkOut)
async def get_link(
    link_and_user: tuple[Link, User] = Depends(require_owner_or_admin),
) -> LinkOut:
    """Get metadata for a specific short link."""
    link, _ = link_and_user
    return LinkOut.model_validate(link)


@router.put("/links/{alias}", response_model=LinkOut)
async def update_link(
    body: LinkUpdate,
    link_and_user: tuple[Link, User] = Depends(require_owner_or_admin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_dep),
) -> LinkOut:
    """Update a short link's destination URL or expiry."""
    link, _ = link_and_user
    fields = body.model_dump(exclude_unset=True)
    if "original_url" in fields and fields["original_url"] is not None:
        fields["original_url"] = str(fields["original_url"])
    updated = await link_service.update_link(db, redis, link, **fields)
    return LinkOut.model_validate(updated)


@router.delete("/links/{alias}", status_code=204)
async def delete_link(
    link_and_user: tuple[Link, User] = Depends(require_owner_or_admin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_dep),
) -> None:
    """Delete a short link."""
    link, _ = link_and_user
    await link_service.delete_link(db, redis, link)
