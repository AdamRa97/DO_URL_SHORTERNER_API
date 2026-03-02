from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserList, UserOut
from app.services import user_service

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserOut, status_code=201)
async def register(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Register a new user account."""
    user = await user_service.register(db, body.email, body.password)
    return UserOut.model_validate(user)


@router.get("/users", response_model=UserList)
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserList:
    """List all users (admin only)."""
    users, total = await user_service.list_users(db, offset, limit)
    return UserList(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserOut:
    """Get a specific user's details (admin only)."""
    user = await user_service.get_user(db, user_id)
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> None:
    """Delete a user and all their links (admin only)."""
    await user_service.delete_user(db, user_id)
