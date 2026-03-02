from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.alias import generate_alias, validate_custom_alias
from app.core.exceptions import AliasConflictError, AliasValidationError, LinkNotFoundError
from app.logger import get_logger
from app.models.link import Link
from app.repositories import link_repo

logger = get_logger(__name__)

_CACHE_TTL = 3600  # seconds


async def create_link(
    db: AsyncSession,
    owner_id: int,
    original_url: str,
    custom_alias: str | None = None,
    expires_at: datetime | None = None,
) -> Link:
    if custom_alias is not None:
        try:
            alias = validate_custom_alias(custom_alias)
        except ValueError as exc:
            raise AliasValidationError(str(exc)) from exc

        existing = await link_repo.get_by_alias(db, alias)
        if existing:
            raise AliasConflictError("This alias is already taken.")
    else:
        # Collision-resistant generation: retry up to 5 times
        for _ in range(5):
            alias = generate_alias(settings.SHORT_CODE_LENGTH)
            if not await link_repo.get_by_alias(db, alias):
                break
        else:
            raise RuntimeError("Failed to generate a unique alias after 5 attempts.")

    link = await link_repo.create(db, alias, original_url, owner_id, expires_at)
    logger.info("link_created", extra={"alias": link.alias, "owner_id": owner_id})
    return link


async def get_link_for_redirect(
    alias: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> str:
    cache_key = f"redirect:{alias}"

    # 1. Check Redis cache first
    cached_url = await redis.get(cache_key)
    if cached_url:
        logger.info("redirect_cache_hit", extra={"alias": alias})
        return cached_url

    # 2. Cache miss — query DB
    link = await link_repo.get_by_alias(db, alias)
    if not link:
        raise LinkNotFoundError()

    # 3. Check expiry
    if link.expires_at and link.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise LinkNotFoundError()

    # 4. Compute TTL (cap at link expiry if set)
    ttl = _CACHE_TTL
    if link.expires_at:
        seconds_left = int(
            (link.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()
        )
        ttl = min(ttl, max(seconds_left, 1))

    await redis.setex(cache_key, ttl, link.original_url)
    logger.info("redirect_cache_miss", extra={"alias": alias})
    return link.original_url


async def get_link_by_alias(db: AsyncSession, alias: str) -> Link:
    link = await link_repo.get_by_alias(db, alias)
    if not link:
        raise LinkNotFoundError()
    return link


async def list_links(
    db: AsyncSession,
    owner_id: int | None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Link], int]:
    if owner_id is None:
        return await link_repo.list_all(db, offset, limit)
    return await link_repo.list_by_owner(db, owner_id, offset, limit)


async def update_link(
    db: AsyncSession,
    redis: aioredis.Redis,
    link: Link,
    **fields,
) -> Link:
    updated = await link_repo.update(db, link, **fields)
    # Synchronously evict cache so stale redirects are not served
    await redis.delete(f"redirect:{link.alias}")
    return updated


async def delete_link(
    db: AsyncSession,
    redis: aioredis.Redis,
    link: Link,
) -> None:
    alias = link.alias
    await link_repo.delete(db, link)
    # Synchronously evict cache
    await redis.delete(f"redirect:{alias}")
    logger.info("link_deleted", extra={"alias": alias})
