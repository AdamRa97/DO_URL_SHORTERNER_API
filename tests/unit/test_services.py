"""Unit tests for all service modules using mocked repositories."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import JWTError

from app.core.exceptions import (
    AliasConflictError,
    AliasValidationError,
    AuthenticationError,
    LinkNotFoundError,
)
from app.models.link import Link
from app.models.user import RoleEnum, User
from app.services import analytics_service, auth_service, link_service, user_service


def _make_user(id=1, email="a@b.com", role=RoleEnum.user, hashed_password="hashed"):
    u = MagicMock(spec=User)
    u.id = id
    u.email = email
    u.role = role
    u.hashed_password = hashed_password
    return u


def _make_link(alias="abc123", original_url="https://example.com", owner_id=1, expires_at=None):
    lnk = MagicMock(spec=Link)
    lnk.alias = alias
    lnk.original_url = original_url
    lnk.owner_id = owner_id
    lnk.expires_at = expires_at
    lnk.id = 1
    return lnk


# ===========================================================================
# link_service
# ===========================================================================

class TestLinkServiceCreate:
    async def test_creates_link_with_generated_alias(self):
        db = AsyncMock()
        link = _make_link()

        with (
            patch("app.services.link_service.generate_alias", return_value="abc123"),
            patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=None),
            patch("app.services.link_service.link_repo.create", new_callable=AsyncMock, return_value=link),
        ):
            result = await link_service.create_link(db, owner_id=1, original_url="https://example.com")

        assert result is link

    async def test_creates_link_with_custom_alias(self):
        db = AsyncMock()
        link = _make_link(alias="myalias")

        with (
            patch("app.services.link_service.validate_custom_alias", return_value="myalias"),
            patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=None),
            patch("app.services.link_service.link_repo.create", new_callable=AsyncMock, return_value=link),
        ):
            result = await link_service.create_link(
                db, owner_id=1, original_url="https://example.com", custom_alias="myalias"
            )

        assert result.alias == "myalias"

    async def test_raises_alias_validation_error_for_invalid_custom_alias(self):
        db = AsyncMock()

        with patch(
            "app.services.link_service.validate_custom_alias",
            side_effect=ValueError("Invalid alias"),
        ):
            with pytest.raises(AliasValidationError):
                await link_service.create_link(
                    db, owner_id=1, original_url="https://x.com", custom_alias="bad!"
                )

    async def test_raises_alias_conflict_error_when_custom_alias_taken(self):
        db = AsyncMock()
        existing = _make_link(alias="taken")

        with (
            patch("app.services.link_service.validate_custom_alias", return_value="taken"),
            patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=existing),
        ):
            with pytest.raises(AliasConflictError):
                await link_service.create_link(
                    db, owner_id=1, original_url="https://x.com", custom_alias="taken"
                )

    async def test_retries_on_alias_collision(self):
        db = AsyncMock()
        link = _make_link()

        # first call (alias collision) → existing link; second call → None
        get_by_alias_mock = AsyncMock(side_effect=[_make_link(), None])

        with (
            patch("app.services.link_service.generate_alias", return_value="abc123"),
            patch("app.services.link_service.link_repo.get_by_alias", get_by_alias_mock),
            patch("app.services.link_service.link_repo.create", new_callable=AsyncMock, return_value=link),
        ):
            result = await link_service.create_link(db, owner_id=1, original_url="https://x.com")

        assert result is link
        assert get_by_alias_mock.await_count == 2

    async def test_raises_runtime_error_after_max_retries(self):
        db = AsyncMock()

        with (
            patch("app.services.link_service.generate_alias", return_value="abc"),
            patch(
                "app.services.link_service.link_repo.get_by_alias",
                new_callable=AsyncMock,
                return_value=_make_link(),  # always collides
            ),
        ):
            with pytest.raises(RuntimeError, match="Failed to generate"):
                await link_service.create_link(db, owner_id=1, original_url="https://x.com")


class TestLinkServiceGetForRedirect:
    async def test_returns_from_cache_when_hit(self):
        db = AsyncMock()
        redis = AsyncMock()
        redis.get.return_value = "https://cached.com"

        result = await link_service.get_link_for_redirect("abc", db, redis)

        assert result == "https://cached.com"
        redis.setex.assert_not_called()

    async def test_queries_db_on_cache_miss(self):
        db = AsyncMock()
        redis = AsyncMock()
        redis.get.return_value = None
        link = _make_link(original_url="https://db.com")

        with patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=link):
            result = await link_service.get_link_for_redirect("abc", db, redis)

        assert result == "https://db.com"
        redis.setex.assert_awaited_once()

    async def test_raises_link_not_found_when_no_link(self):
        db = AsyncMock()
        redis = AsyncMock()
        redis.get.return_value = None

        with patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=None):
            with pytest.raises(LinkNotFoundError):
                await link_service.get_link_for_redirect("missing", db, redis)

    async def test_raises_link_not_found_when_expired(self):
        db = AsyncMock()
        redis = AsyncMock()
        redis.get.return_value = None
        expires = datetime.now(timezone.utc) - timedelta(hours=1)
        link = _make_link(expires_at=expires)

        with patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=link):
            with pytest.raises(LinkNotFoundError):
                await link_service.get_link_for_redirect("abc", db, redis)

    async def test_caps_ttl_at_expiry(self):
        db = AsyncMock()
        redis = AsyncMock()
        redis.get.return_value = None
        # Link expires in 60 seconds (less than _CACHE_TTL of 3600)
        expires = datetime.now(timezone.utc) + timedelta(seconds=60)
        link = _make_link(expires_at=expires)

        with patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=link):
            await link_service.get_link_for_redirect("abc", db, redis)

        call_args = redis.setex.call_args
        ttl_used = call_args[0][1]
        assert ttl_used <= 60


class TestLinkServiceGetByAlias:
    async def test_returns_link(self):
        db = AsyncMock()
        link = _make_link()

        with patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=link):
            result = await link_service.get_link_by_alias(db, "abc123")

        assert result is link

    async def test_raises_link_not_found(self):
        db = AsyncMock()

        with patch("app.services.link_service.link_repo.get_by_alias", new_callable=AsyncMock, return_value=None):
            with pytest.raises(LinkNotFoundError):
                await link_service.get_link_by_alias(db, "missing")


class TestLinkServiceList:
    async def test_list_by_owner(self):
        db = AsyncMock()
        links = [_make_link()]

        with patch(
            "app.services.link_service.link_repo.list_by_owner",
            new_callable=AsyncMock,
            return_value=(links, 1),
        ):
            result, total = await link_service.list_links(db, owner_id=1)

        assert result == links
        assert total == 1

    async def test_list_all_when_no_owner(self):
        db = AsyncMock()
        links = [_make_link()]

        with patch(
            "app.services.link_service.link_repo.list_all",
            new_callable=AsyncMock,
            return_value=(links, 1),
        ):
            result, total = await link_service.list_links(db, owner_id=None)

        assert result == links
        assert total == 1


class TestLinkServiceUpdate:
    async def test_updates_and_evicts_cache(self):
        db = AsyncMock()
        redis = AsyncMock()
        link = _make_link()
        updated = _make_link(original_url="https://new.com")

        with patch("app.services.link_service.link_repo.update", new_callable=AsyncMock, return_value=updated):
            result = await link_service.update_link(db, redis, link, original_url="https://new.com")

        assert result is updated
        redis.delete.assert_awaited_once_with(f"redirect:{link.alias}")


class TestLinkServiceDelete:
    async def test_deletes_and_evicts_cache(self):
        db = AsyncMock()
        redis = AsyncMock()
        link = _make_link(alias="abc123")

        with patch("app.services.link_service.link_repo.delete", new_callable=AsyncMock):
            await link_service.delete_link(db, redis, link)

        redis.delete.assert_awaited_once_with("redirect:abc123")


# ===========================================================================
# auth_service
# ===========================================================================

class TestAuthServiceLogin:
    async def test_returns_tokens_on_success(self):
        db = AsyncMock()
        user = _make_user()

        with (
            patch("app.services.auth_service.user_repo.get_by_email", new_callable=AsyncMock, return_value=user),
            patch("app.services.auth_service.verify_password", return_value=True),
            patch("app.services.auth_service.create_access_token", return_value="access-token"),
            patch("app.services.auth_service.create_refresh_token", return_value=("refresh-token", "jti-123")),
            patch("app.services.auth_service.token_repo.create", new_callable=AsyncMock),
        ):
            access, refresh = await auth_service.login(db, "a@b.com", "password")

        assert access == "access-token"
        assert refresh == "refresh-token"

    async def test_raises_auth_error_when_user_not_found(self):
        db = AsyncMock()

        with patch("app.services.auth_service.user_repo.get_by_email", new_callable=AsyncMock, return_value=None):
            with pytest.raises(AuthenticationError):
                await auth_service.login(db, "missing@b.com", "password")

    async def test_raises_auth_error_when_wrong_password(self):
        db = AsyncMock()
        user = _make_user()

        with (
            patch("app.services.auth_service.user_repo.get_by_email", new_callable=AsyncMock, return_value=user),
            patch("app.services.auth_service.verify_password", return_value=False),
        ):
            with pytest.raises(AuthenticationError):
                await auth_service.login(db, "a@b.com", "wrong")


class TestAuthServiceRefresh:
    async def test_returns_new_access_token(self):
        db = AsyncMock()
        user = _make_user()
        from app.models.refresh_token import RefreshToken
        stored_token = MagicMock(spec=RefreshToken)
        stored_token.revoked = False
        stored_token.user_id = 1

        with (
            patch("app.services.auth_service.decode_token", return_value={"type": "refresh", "jti": "jti-abc"}),
            patch("app.services.auth_service.token_repo.get_by_jti", new_callable=AsyncMock, return_value=stored_token),
            patch("app.services.auth_service.user_repo.get_by_id", new_callable=AsyncMock, return_value=user),
            patch("app.services.auth_service.create_access_token", return_value="new-access"),
        ):
            result = await auth_service.refresh_access_token(db, "refresh-token")

        assert result == "new-access"

    async def test_raises_auth_error_on_invalid_token(self):
        db = AsyncMock()

        with patch("app.services.auth_service.decode_token", side_effect=JWTError("bad")):
            with pytest.raises(AuthenticationError):
                await auth_service.refresh_access_token(db, "bad-token")

    async def test_raises_auth_error_when_wrong_token_type(self):
        db = AsyncMock()

        with patch("app.services.auth_service.decode_token", return_value={"type": "access", "jti": "x"}):
            with pytest.raises(AuthenticationError):
                await auth_service.refresh_access_token(db, "access-token")

    async def test_raises_auth_error_when_no_jti(self):
        db = AsyncMock()

        with patch("app.services.auth_service.decode_token", return_value={"type": "refresh"}):
            with pytest.raises(AuthenticationError):
                await auth_service.refresh_access_token(db, "token-no-jti")

    async def test_raises_auth_error_when_token_revoked(self):
        db = AsyncMock()
        from app.models.refresh_token import RefreshToken
        stored = MagicMock(spec=RefreshToken)
        stored.revoked = True

        with (
            patch("app.services.auth_service.decode_token", return_value={"type": "refresh", "jti": "jti"}),
            patch("app.services.auth_service.token_repo.get_by_jti", new_callable=AsyncMock, return_value=stored),
        ):
            with pytest.raises(AuthenticationError):
                await auth_service.refresh_access_token(db, "revoked-token")

    async def test_raises_auth_error_when_token_not_in_db(self):
        db = AsyncMock()

        with (
            patch("app.services.auth_service.decode_token", return_value={"type": "refresh", "jti": "jti"}),
            patch("app.services.auth_service.token_repo.get_by_jti", new_callable=AsyncMock, return_value=None),
        ):
            with pytest.raises(AuthenticationError):
                await auth_service.refresh_access_token(db, "unknown-token")

    async def test_raises_auth_error_when_user_not_found(self):
        db = AsyncMock()
        from app.models.refresh_token import RefreshToken
        stored = MagicMock(spec=RefreshToken)
        stored.revoked = False
        stored.user_id = 999

        with (
            patch("app.services.auth_service.decode_token", return_value={"type": "refresh", "jti": "jti"}),
            patch("app.services.auth_service.token_repo.get_by_jti", new_callable=AsyncMock, return_value=stored),
            patch("app.services.auth_service.user_repo.get_by_id", new_callable=AsyncMock, return_value=None),
        ):
            with pytest.raises(AuthenticationError):
                await auth_service.refresh_access_token(db, "orphaned-token")


class TestAuthServiceLogout:
    async def test_revokes_valid_token(self):
        db = AsyncMock()
        from app.models.refresh_token import RefreshToken
        stored = MagicMock(spec=RefreshToken)
        stored.revoked = False
        stored.user_id = 1

        with (
            patch("app.services.auth_service.decode_token", return_value={"type": "refresh", "jti": "jti-abc"}),
            patch("app.services.auth_service.token_repo.get_by_jti", new_callable=AsyncMock, return_value=stored),
            patch("app.services.auth_service.token_repo.revoke", new_callable=AsyncMock) as mock_revoke,
        ):
            await auth_service.logout(db, "refresh-token")

        mock_revoke.assert_awaited_once_with(db, stored)

    async def test_silently_succeeds_on_invalid_token(self):
        db = AsyncMock()

        with patch("app.services.auth_service.decode_token", side_effect=JWTError("bad")):
            await auth_service.logout(db, "bad-token")  # Should not raise

    async def test_silently_succeeds_when_no_jti(self):
        db = AsyncMock()

        with patch("app.services.auth_service.decode_token", return_value={"type": "refresh"}):
            await auth_service.logout(db, "no-jti")

    async def test_silently_succeeds_when_already_revoked(self):
        db = AsyncMock()
        from app.models.refresh_token import RefreshToken
        stored = MagicMock(spec=RefreshToken)
        stored.revoked = True

        with (
            patch("app.services.auth_service.decode_token", return_value={"type": "refresh", "jti": "jti"}),
            patch("app.services.auth_service.token_repo.get_by_jti", new_callable=AsyncMock, return_value=stored),
            patch("app.services.auth_service.token_repo.revoke", new_callable=AsyncMock) as mock_revoke,
        ):
            await auth_service.logout(db, "token")

        mock_revoke.assert_not_called()

    async def test_silently_succeeds_when_token_not_in_db(self):
        db = AsyncMock()

        with (
            patch("app.services.auth_service.decode_token", return_value={"type": "refresh", "jti": "jti"}),
            patch("app.services.auth_service.token_repo.get_by_jti", new_callable=AsyncMock, return_value=None),
        ):
            await auth_service.logout(db, "unknown")  # Should not raise


# ===========================================================================
# user_service
# ===========================================================================

class TestUserServiceRegister:
    async def test_registers_new_user(self):
        db = AsyncMock()
        user = _make_user()

        with (
            patch("app.services.user_service.user_repo.get_by_email", new_callable=AsyncMock, return_value=None),
            patch("app.services.user_service.hash_password", return_value="hashed"),
            patch("app.services.user_service.user_repo.create", new_callable=AsyncMock, return_value=user),
        ):
            result = await user_service.register(db, "a@b.com", "password")

        assert result is user

    async def test_raises_http_400_when_email_taken(self):
        db = AsyncMock()
        existing = _make_user()

        with patch("app.services.user_service.user_repo.get_by_email", new_callable=AsyncMock, return_value=existing):
            with pytest.raises(HTTPException) as exc_info:
                await user_service.register(db, "a@b.com", "password")

        assert exc_info.value.status_code == 400


class TestUserServiceGetUser:
    async def test_returns_user(self):
        db = AsyncMock()
        user = _make_user()

        with patch("app.services.user_service.user_repo.get_by_id", new_callable=AsyncMock, return_value=user):
            result = await user_service.get_user(db, 1)

        assert result is user

    async def test_raises_http_404_when_not_found(self):
        db = AsyncMock()

        with patch("app.services.user_service.user_repo.get_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await user_service.get_user(db, 999)

        assert exc_info.value.status_code == 404


class TestUserServiceListUsers:
    async def test_returns_users_and_total(self):
        db = AsyncMock()
        users = [_make_user()]

        with patch(
            "app.services.user_service.user_repo.list_paginated",
            new_callable=AsyncMock,
            return_value=(users, 1),
        ):
            result, total = await user_service.list_users(db)

        assert result == users
        assert total == 1


class TestUserServiceDeleteUser:
    async def test_deletes_user(self):
        db = AsyncMock()
        user = _make_user()

        with (
            patch("app.services.user_service.user_repo.get_by_id", new_callable=AsyncMock, return_value=user),
            patch("app.services.user_service.user_repo.delete", new_callable=AsyncMock) as mock_delete,
        ):
            await user_service.delete_user(db, 1)

        mock_delete.assert_awaited_once_with(db, user)

    async def test_raises_http_404_when_not_found(self):
        db = AsyncMock()

        with patch("app.services.user_service.user_repo.get_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await user_service.delete_user(db, 999)

        assert exc_info.value.status_code == 404


# ===========================================================================
# analytics_service
# ===========================================================================

class TestAnalyticsService:
    async def test_returns_stats(self):
        db = AsyncMock()

        with (
            patch("app.services.analytics_service.click_repo.count_by_link", new_callable=AsyncMock, return_value=10),
            patch("app.services.analytics_service.click_repo.count_unique_ips", new_callable=AsyncMock, return_value=4),
        ):
            stats = await analytics_service.get_stats(db, link_id=1)

        assert stats == {"total_clicks": 10, "unique_ips": 4}

    async def test_returns_zero_stats_for_new_link(self):
        db = AsyncMock()

        with (
            patch("app.services.analytics_service.click_repo.count_by_link", new_callable=AsyncMock, return_value=0),
            patch("app.services.analytics_service.click_repo.count_unique_ips", new_callable=AsyncMock, return_value=0),
        ):
            stats = await analytics_service.get_stats(db, link_id=99)

        assert stats["total_clicks"] == 0
        assert stats["unique_ips"] == 0