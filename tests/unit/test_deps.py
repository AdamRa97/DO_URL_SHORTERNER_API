"""Unit tests for app/api/deps.py."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import JWTError

from app.core.exceptions import AuthenticationError, AuthorizationError, LinkNotFoundError
from app.models.link import Link
from app.models.user import RoleEnum, User


def _make_user(id=1, role=RoleEnum.user):
    u = MagicMock(spec=User)
    u.id = id
    u.role = role
    return u


def _make_link(alias="abc", owner_id=1):
    lnk = MagicMock(spec=Link)
    lnk.alias = alias
    lnk.owner_id = owner_id
    return lnk


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    async def test_returns_user_for_valid_token(self):
        from app.api.deps import get_current_user

        user = _make_user(id=5)
        db = AsyncMock()

        with (
            patch("app.api.deps.decode_token", return_value={"type": "access", "sub": "5"}),
            patch("app.api.deps.user_repo.get_by_id", new_callable=AsyncMock, return_value=user),
        ):
            result = await get_current_user(token="valid-token", db=db)

        assert result is user

    async def test_raises_auth_error_when_token_type_is_refresh(self):
        from app.api.deps import get_current_user

        db = AsyncMock()

        with patch("app.api.deps.decode_token", return_value={"type": "refresh", "sub": "1"}):
            with pytest.raises(AuthenticationError):
                await get_current_user(token="refresh-token", db=db)

    async def test_raises_auth_error_on_jwt_error(self):
        from app.api.deps import get_current_user

        db = AsyncMock()

        with patch("app.api.deps.decode_token", side_effect=JWTError("bad")):
            with pytest.raises(AuthenticationError):
                await get_current_user(token="bad-token", db=db)

    async def test_raises_auth_error_when_sub_missing(self):
        from app.api.deps import get_current_user

        db = AsyncMock()

        with patch("app.api.deps.decode_token", return_value={"type": "access"}):
            with pytest.raises(AuthenticationError):
                await get_current_user(token="no-sub-token", db=db)

    async def test_raises_auth_error_when_user_not_found(self):
        from app.api.deps import get_current_user

        db = AsyncMock()

        with (
            patch("app.api.deps.decode_token", return_value={"type": "access", "sub": "999"}),
            patch("app.api.deps.user_repo.get_by_id", new_callable=AsyncMock, return_value=None),
        ):
            with pytest.raises(AuthenticationError):
                await get_current_user(token="orphaned-token", db=db)


# ---------------------------------------------------------------------------
# require_admin
# ---------------------------------------------------------------------------

class TestRequireAdmin:
    async def test_returns_admin_user(self):
        from app.api.deps import require_admin

        admin = _make_user(role=RoleEnum.admin)

        result = await require_admin(current_user=admin)

        assert result is admin

    async def test_raises_authorization_error_for_non_admin(self):
        from app.api.deps import require_admin

        user = _make_user(role=RoleEnum.user)

        with pytest.raises(AuthorizationError):
            await require_admin(current_user=user)


# ---------------------------------------------------------------------------
# require_owner_or_admin
# ---------------------------------------------------------------------------

class TestRequireOwnerOrAdmin:
    async def test_returns_link_and_user_when_owner(self):
        from app.api.deps import require_owner_or_admin

        user = _make_user(id=1, role=RoleEnum.user)
        link = _make_link(alias="abc", owner_id=1)
        db = AsyncMock()

        with patch("app.api.deps.link_repo.get_by_alias", new_callable=AsyncMock, return_value=link):
            result_link, result_user = await require_owner_or_admin("abc", current_user=user, db=db)

        assert result_link is link
        assert result_user is user

    async def test_returns_link_and_user_when_admin(self):
        from app.api.deps import require_owner_or_admin

        admin = _make_user(id=99, role=RoleEnum.admin)
        link = _make_link(alias="abc", owner_id=1)  # owned by different user
        db = AsyncMock()

        with patch("app.api.deps.link_repo.get_by_alias", new_callable=AsyncMock, return_value=link):
            result_link, result_user = await require_owner_or_admin("abc", current_user=admin, db=db)

        assert result_link is link

    async def test_raises_link_not_found_when_link_missing(self):
        from app.api.deps import require_owner_or_admin

        user = _make_user(id=1, role=RoleEnum.user)
        db = AsyncMock()

        with patch("app.api.deps.link_repo.get_by_alias", new_callable=AsyncMock, return_value=None):
            with pytest.raises(LinkNotFoundError):
                await require_owner_or_admin("missing", current_user=user, db=db)

    async def test_raises_link_not_found_for_other_users_link(self):
        from app.api.deps import require_owner_or_admin

        user = _make_user(id=1, role=RoleEnum.user)
        link = _make_link(alias="abc", owner_id=2)  # owned by user 2
        db = AsyncMock()

        with patch("app.api.deps.link_repo.get_by_alias", new_callable=AsyncMock, return_value=link):
            with pytest.raises(LinkNotFoundError):
                await require_owner_or_admin("abc", current_user=user, db=db)