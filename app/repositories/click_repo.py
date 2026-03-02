from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click import Click


async def create(
    db: AsyncSession,
    link_id: int,
    ip_hash: str | None,
    user_agent: str | None,
    referer: str | None,
) -> Click:
    click = Click(link_id=link_id, ip_hash=ip_hash, user_agent=user_agent, referer=referer)
    db.add(click)
    await db.commit()
    await db.refresh(click)
    return click


async def count_by_link(db: AsyncSession, link_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(Click).where(Click.link_id == link_id)
    )
    return result.scalar_one()


async def count_unique_ips(db: AsyncSession, link_id: int) -> int:
    result = await db.execute(
        select(func.count(distinct(Click.ip_hash)))
        .select_from(Click)
        .where(Click.link_id == link_id)
    )
    return result.scalar_one()
