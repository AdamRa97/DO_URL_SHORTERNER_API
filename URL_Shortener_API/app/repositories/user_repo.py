from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RoleEnum, User


async def create(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    role: RoleEnum = RoleEnum.user,
) -> User:
    user = User(email=email, hashed_password=hashed_password, role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def list_paginated(
    db: AsyncSession, offset: int = 0, limit: int = 20
) -> tuple[list[User], int]:
    rows = await db.execute(select(User).offset(offset).limit(limit))
    users = list(rows.scalars().all())
    total_result = await db.execute(select(func.count()).select_from(User))
    total = total_result.scalar_one()
    return users, total


async def delete(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.commit()
