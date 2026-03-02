from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.token import AccessTokenResponse, RefreshRequest, TokenResponse
from app.services import auth_service

router = APIRouter(tags=["tokens"])


@router.post("/tokens", response_model=TokenResponse, status_code=200)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login with email + password. Returns access and refresh JWT tokens."""
    access_token, refresh_token = await auth_service.login(db, form.username, form.password)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.put("/tokens", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """Exchange a valid refresh token for a new access token."""
    access_token = await auth_service.refresh_access_token(db, body.refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.delete("/tokens", status_code=204)
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    """Logout — invalidate the refresh token."""
    await auth_service.logout(db, body.refresh_token)
