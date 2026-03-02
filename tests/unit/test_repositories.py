"""Unit tests for all repository modules using mocked AsyncSession."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.link import Link
from app.models.refresh_token import RefreshToken
from app.models.user import RoleEnum, User
from app.repositories import click_repo, link_repo, token_repo, user_repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_async_result(value):
    """Return a mock that behaves like an awaited SQLAlchemy Result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value.all.return_value = [value] if value is not None else []
    return result


def _make_db():
    """Return a mock AsyncSession."""
    db = AsyncMock()
    return db


# ===========================================================================
# user_repo
# ===========================================================================

class TestUserRepoCreate:
    async def test_creates_and_returns_user(self):
        db = _make_db()
        user = User(id=1, email="a@b.com", hashed_password="hash", role=RoleEnum.user)
        db.refresh.side_effect = lambda u: None

        with patch("app.repositories.user_repo.User", return_value=user):
            result = await user_repo.create(db, "a@b.com", "hash")

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    async def test_creates_admin_user(self):
        db = _make_db()
        user = User(id=2, email="admin@b.com", hashed_password="hash", role=RoleEnum.admin)
        db.refresh.side_effect = lambda u: None

        with patch("app.repositories.user_repo.User", return_value=user):
            result = await user_repo.create(db, "admin@b.com", "hash", role=RoleEnum.admin)

        db.add.assert_called_once()
        db.commit.assert_awaited_once()


class TestUserRepoGetById:
    async def test_returns_user_when_found(self):
        db = _make_db()
        user = User(id=1, email="a@b.com", hashed_password="x", role=RoleEnum.user)
        db.execute.return_value = _make_async_result(user)

        result = await user_repo.get_by_id(db, 1)
        assert result is user

    async def test_returns_none_when_not_found(self):
        db = _make_db()
        db.execute.return_value = _make_async_result(None)

        result = await user_repo.get_by_id(db, 999)
        assert result is None


class TestUserRepoGetByEmail:
    async def test_returns_user_when_found(self):
        db = _make_db()
        user = User(id=1, email="a@b.com", hashed_password="x", role=RoleEnum.user)
        db.execute.return_value = _make_async_result(user)

        result = await user_repo.get_by_email(db, "a@b.com")
        assert result is user

    async def test_returns_none_when_not_found(self):
        db = _make_db()
        db.execute.return_value = _make_async_result(None)

        result = await user_repo.get_by_email(db, "missing@b.com")
        assert result is None


class TestUserRepoListPaginated:
    async def test_returns_users_and_total(self):
        db = _make_db()
        user = User(id=1, email="a@b.com", hashed_password="x", role=RoleEnum.user)

        first_result = MagicMock()
        first_result.scalars.return_value.all.return_value = [user]

        second_result = MagicMock()
        second_result.scalar_one.return_value = 1

        db.execute.side_effect = [first_result, second_result]

        users, total = await user_repo.list_paginated(db, offset=0, limit=20)
        assert users == [user]
        assert total == 1

    async def test_returns_empty_list(self):
        db = _make_db()

        first_result = MagicMock()
        first_result.scalars.return_value.all.return_value = []

        second_result = MagicMock()
        second_result.scalar_one.return_value = 0

        db.execute.side_effect = [first_result, second_result]

        users, total = await user_repo.list_paginated(db)
        assert users == []
        assert total == 0


class TestUserRepoDelete:
    async def test_deletes_user(self):
        db = _make_db()
        user = User(id=1, email="a@b.com", hashed_password="x", role=RoleEnum.user)

        await user_repo.delete(db, user)
        db.delete.assert_awaited_once_with(user)
        db.commit.assert_awaited_once()


# ===========================================================================
# link_repo
# ===========================================================================

class TestLinkRepoCreate:
    async def test_creates_link(self):
        db = _make_db()
        link = Link(id=1, alias="abc123", original_url="https://example.com", owner_id=1)
        db.refresh.side_effect = lambda l: None

        with patch("app.repositories.link_repo.Link", return_value=link):
            result = await link_repo.create(db, "abc123", "https://example.com", 1)

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    async def test_creates_link_with_expiry(self):
        db = _make_db()
        expires = datetime(2030, 1, 1, tzinfo=timezone.utc)
        link = Link(alias="abc123", original_url="https://x.com", owner_id=1, expires_at=expires)
        db.refresh.side_effect = lambda l: None

        with patch("app.repositories.link_repo.Link", return_value=link):
            await link_repo.create(db, "abc123", "https://x.com", 1, expires_at=expires)

        db.add.assert_called_once()
        db.commit.assert_awaited_once()


class TestLinkRepoGetByAlias:
    async def test_returns_link_when_found(self):
        db = _make_db()
        link = Link(alias="abc", original_url="https://x.com", owner_id=1)
        db.execute.return_value = _make_async_result(link)

        result = await link_repo.get_by_alias(db, "abc")
        assert result is link

    async def test_returns_none_when_not_found(self):
        db = _make_db()
        db.execute.return_value = _make_async_result(None)

        result = await link_repo.get_by_alias(db, "missing")
        assert result is None


class TestLinkRepoListByOwner:
    async def test_returns_links_and_total(self):
        db = _make_db()
        link = Link(alias="abc", original_url="https://x.com", owner_id=5)

        first_result = MagicMock()
        first_result.scalars.return_value.all.return_value = [link]

        second_result = MagicMock()
        second_result.scalar_one.return_value = 1

        db.execute.side_effect = [first_result, second_result]

        links, total = await link_repo.list_by_owner(db, owner_id=5)
        assert links == [link]
        assert total == 1


class TestLinkRepoListAll:
    async def test_returns_all_links_and_total(self):
        db = _make_db()
        link = Link(alias="abc", original_url="https://x.com", owner_id=1)

        first_result = MagicMock()
        first_result.scalars.return_value.all.return_value = [link]

        second_result = MagicMock()
        second_result.scalar_one.return_value = 1

        db.execute.side_effect = [first_result, second_result]

        links, total = await link_repo.list_all(db)
        assert links == [link]
        assert total == 1


class TestLinkRepoUpdate:
    async def test_updates_fields(self):
        db = _make_db()
        link = Link(alias="abc", original_url="https://old.com", owner_id=1)
        db.refresh.side_effect = lambda l: None

        result = await link_repo.update(db, link, original_url="https://new.com")

        assert link.original_url == "https://new.com"
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(link)


class TestLinkRepoDelete:
    async def test_deletes_link(self):
        db = _make_db()
        link = Link(alias="abc", original_url="https://x.com", owner_id=1)

        await link_repo.delete(db, link)
        db.delete.assert_awaited_once_with(link)
        db.commit.assert_awaited_once()


# ===========================================================================
# click_repo
# ===========================================================================

class TestClickRepoCreate:
    async def test_creates_click(self):
        from app.models.click import Click
        db = _make_db()
        click = Click(id=1, link_id=1, ip_hash="abc", user_agent="ua", referer="ref")
        db.refresh.side_effect = lambda c: None

        with patch("app.repositories.click_repo.Click", return_value=click):
            result = await click_repo.create(db, 1, "abc", "ua", "ref")

        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    async def test_creates_click_with_none_values(self):
        from app.models.click import Click
        db = _make_db()
        click = Click(id=1, link_id=1, ip_hash=None, user_agent=None, referer=None)
        db.refresh.side_effect = lambda c: None

        with patch("app.repositories.click_repo.Click", return_value=click):
            await click_repo.create(db, 1, None, None, None)

        db.add.assert_called_once()


class TestClickRepoCount:
    async def test_count_by_link(self):
        db = _make_db()
        db.execute.return_value = _make_async_result(5)

        count = await click_repo.count_by_link(db, link_id=1)
        assert count == 5

    async def test_count_unique_ips(self):
        db = _make_db()
        db.execute.return_value = _make_async_result(3)

        count = await click_repo.count_unique_ips(db, link_id=1)
        assert count == 3


# ===========================================================================
# token_repo
# ===========================================================================

class TestTokenRepoCreate:
    async def test_creates_token(self):
        db = _make_db()
        expires = datetime(2030, 1, 1, tzinfo=timezone.utc)
        token = RefreshToken(jti="jti-abc", user_id=1, expires_at=expires)
        db.refresh.side_effect = lambda t: None

        with patch("app.repositories.token_repo.RefreshToken", return_value=token):
            result = await token_repo.create(db, "jti-abc", user_id=1, expires_at=expires)

        db.add.assert_called_once()
        db.commit.assert_awaited_once()


class TestTokenRepoGetByJti:
    async def test_returns_token_when_found(self):
        db = _make_db()
        expires = datetime(2030, 1, 1, tzinfo=timezone.utc)
        token = RefreshToken(jti="jti-abc", user_id=1, expires_at=expires)
        db.execute.return_value = _make_async_result(token)

        result = await token_repo.get_by_jti(db, "jti-abc")
        assert result is token

    async def test_returns_none_when_not_found(self):
        db = _make_db()
        db.execute.return_value = _make_async_result(None)

        result = await token_repo.get_by_jti(db, "missing-jti")
        assert result is None


class TestTokenRepoRevoke:
    async def test_revokes_token(self):
        db = _make_db()
        expires = datetime(2030, 1, 1, tzinfo=timezone.utc)
        token = RefreshToken(jti="jti-abc", user_id=1, expires_at=expires, revoked=False)

        await token_repo.revoke(db, token)

        assert token.revoked is True
        db.commit.assert_awaited_once()


class TestTokenRepoRevokeAll:
    async def test_revokes_all_for_user(self):
        db = _make_db()

        await token_repo.revoke_all_for_user(db, user_id=1)

        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()