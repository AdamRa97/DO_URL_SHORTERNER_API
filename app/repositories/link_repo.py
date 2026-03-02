from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.link import Link


async def create(
    db: AsyncSession,
    alias: str,
    original_url: str,
    owner_id: int,
    expires_at: datetime | None = None,
) -> Link:
    link = Link(alias=alias, original_url=original_url, owner_id=owner_id, expires_at=expires_at)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def get_by_alias(db: AsyncSession, alias: str) -> Link | None:
    result = await db.execute(select(Link).where(Link.alias == alias))
    return result.scalar_one_or_none()


async def list_by_owner(
    db: AsyncSession, owner_id: int, offset: int = 0, limit: int = 20
) -> tuple[list[Link], int]:
    rows = await db.execute(
        select(Link).where(Link.owner_id == owner_id).offset(offset).limit(limit)
    )
    links = list(rows.scalars().all())
    total_result = await db.execute(
        select(func.count()).select_from(Link).where(Link.owner_id == owner_id)
    )
    total = total_result.scalar_one()
    return links, total


async def list_all(
    db: AsyncSession, offset: int = 0, limit: int = 20
) -> tuple[list[Link], int]:
    rows = await db.execute(select(Link).offset(offset).limit(limit))
    links = list(rows.scalars().all())
    total_result = await db.execute(select(func.count()).select_from(Link))
    total = total_result.scalar_one()
    return links, total


async def update(db: AsyncSession, link: Link, **fields) -> Link:
    for key, value in fields.items():
        setattr(link, key, value)
    await db.commit()
    await db.refresh(link)
    return link


async def delete(db: AsyncSession, link: Link) -> None:
    await db.delete(link)
    await db.commit()
