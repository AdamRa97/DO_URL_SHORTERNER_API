from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.logger import get_logger
from app.repositories import token_repo, user_repo

logger = get_logger(__name__)


async def login(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[str, str]:
    """Authenticate a user and issue access + refresh tokens.

    Always raises AuthenticationError with the same message on failure —
    never distinguish "user not found" from "wrong password".
    """
    user = await user_repo.get_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise AuthenticationError()

    access_token = create_access_token(user.id, user.role.value)
    refresh_token_str, jti = create_refresh_token()

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=10  # slightly beyond REFRESH_TOKEN_EXPIRE_DAYS for DB record retention
    )
    await token_repo.create(db, jti=jti, user_id=user.id, expires_at=expires_at)

    logger.info("user_logged_in", extra={"user_id": user.id})
    return access_token, refresh_token_str


async def refresh_access_token(db: AsyncSession, refresh_token_str: str) -> str:
    """Exchange a valid refresh token for a new access token."""
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        raise AuthenticationError()

    if payload.get("type") != "refresh":
        raise AuthenticationError()

    jti = payload.get("jti")
    if not jti:
        raise AuthenticationError()

    stored = await token_repo.get_by_jti(db, jti)
    if not stored or stored.revoked:
        raise AuthenticationError()

    user = await user_repo.get_by_id(db, stored.user_id)
    if not user:
        raise AuthenticationError()

    return create_access_token(user.id, user.role.value)


async def logout(db: AsyncSession, refresh_token_str: str) -> None:
    """Invalidate a refresh token. Silently succeeds even if already revoked."""
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        return  # Already invalid — nothing to revoke

    jti = payload.get("jti")
    if not jti:
        return

    stored = await token_repo.get_by_jti(db, jti)
    if stored and not stored.revoked:
        await token_repo.revoke(db, stored)
        logger.info("user_logged_out", extra={"user_id": stored.user_id})
