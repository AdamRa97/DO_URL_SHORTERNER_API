from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError, LinkNotFoundError
from app.core.security import decode_token
from app.database import get_db
from app.models.link import Link
from app.models.user import RoleEnum, User
from app.repositories import link_repo, user_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/tokens")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate the Bearer access token and return the authenticated user.

    Maps ALL JWTError subtypes to AuthenticationError (401) —
    never distinguishes expired vs invalid vs tampered.
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise AuthenticationError()
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise AuthenticationError()

    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise AuthenticationError()

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != RoleEnum.admin:
        raise AuthorizationError()
    return current_user


async def require_owner_or_admin(
    alias: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[Link, User]:
    """Return (link, user) if the caller owns the link or is an admin.

    Returns 404 in BOTH cases — link missing AND link belonging to another user.
    This prevents resource enumeration (403 would reveal the alias exists).
    """
    link = await link_repo.get_by_alias(db, alias)
    if not link or (
        link.owner_id != current_user.id and current_user.role != RoleEnum.admin
    ):
        raise LinkNotFoundError()
    return link, current_user
