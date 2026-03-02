from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import click_repo


async def get_stats(db: AsyncSession, link_id: int) -> dict:
    total_clicks = await click_repo.count_by_link(db, link_id)
    unique_ips = await click_repo.count_unique_ips(db, link_id)
    return {
        "total_clicks": total_clicks,
        "unique_ips": unique_ips,
    }
