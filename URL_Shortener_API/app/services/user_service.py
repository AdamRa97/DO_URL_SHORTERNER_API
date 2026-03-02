from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.logger import get_logger
from app.models.user import RoleEnum, User
from app.repositories import user_repo

logger = get_logger(__name__)


async def register(db: AsyncSession, email: str, password: str) -> User:
    """Register a new user. Returns 400 if the email is already registered
    (generic message — does not confirm whether the email exists).
    """
    existing = await user_repo.get_by_email(db, email)
    if existing:
        # Generic error so bad actors cannot enumerate registered emails
        raise HTTPException(status_code=400, detail="Registration failed. Please try again.")

    hashed = hash_password(password)
    user = await user_repo.create(db, email=email, hashed_password=hashed, role=RoleEnum.user)
    logger.info("user_registered", extra={"user_id": user.id})
    return user


async def get_user(db: AsyncSession, user_id: int) -> User:
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def list_users(
    db: AsyncSession, offset: int = 0, limit: int = 20
) -> tuple[list[User], int]:
    return await user_repo.list_paginated(db, offset, limit)


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await user_repo.delete(db, user)
    logger.info("user_deleted", extra={"user_id": user_id})
