import hashlib

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.logger import get_logger
from app.models.click import Click
from app.models.link import Link
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


def _hash_ip(ip: str | None) -> str | None:
    """SHA-256 of the raw IP address. Stores a pseudonymised value, not PII."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def record_click(
    self,
    alias: str,
    raw_ip: str | None,
    user_agent: str | None,
    referer: str | None,
) -> None:
    """Write a Click row for the given alias.

    Uses a synchronous SQLAlchemy session (psycopg2) because Celery workers
    are synchronous. Retries up to 3 times on DB error.
    """
    try:
        with SyncSessionLocal() as db:
            link = db.execute(
                select(Link).where(Link.alias == alias)
            ).scalar_one_or_none()
            if not link:
                logger.warning("record_click_link_not_found", extra={"alias": alias})
                return
            click = Click(
                link_id=link.id,
                ip_hash=_hash_ip(raw_ip),
                user_agent=user_agent[:512] if user_agent else None,
                referer=referer[:2048] if referer else None,
            )
            db.add(click)
            db.commit()
    except Exception as exc:
        logger.error("record_click_error", extra={"alias": alias, "error": str(exc)})
        raise self.retry(exc=exc)
