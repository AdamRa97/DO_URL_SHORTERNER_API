import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/tokens",
            data={"username": "testuser@example.com", "password": "SecurePass1!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/tokens",
            data={"username": "testuser@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 401
        # Must be the same generic message — does not reveal "wrong password"
        assert resp.json()["detail"] == "Invalid credentials"

    async def test_login_unknown_email_returns_same_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tokens",
            data={"username": "nobody@example.com", "password": "irrelevant"},
        )
        assert resp.status_code == 401
        # Same message as wrong password — never distinguishes the two cases
        assert resp.json()["detail"] == "Invalid credentials"

    async def test_login_missing_fields_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/tokens", data={})
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestRefresh:
    async def test_refresh_issues_new_access_token(self, client: AsyncClient, registered_user):
        login = await client.post(
            "/api/v1/tokens",
            data={"username": "testuser@example.com", "password": "SecurePass1!"},
        )
        refresh_token = login.json()["refresh_token"]

        resp = await client.put(
            "/api/v1/tokens",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_invalid_refresh_token_returns_401(self, client: AsyncClient):
        resp = await client.put(
            "/api/v1/tokens",
            json={"refresh_token": "not.a.valid.token"},
        )
        assert resp.status_code == 401

    async def test_access_token_cannot_be_used_as_refresh(
        self, client: AsyncClient, user_token: str
    ):
        resp = await client.put(
            "/api/v1/tokens",
            json={"refresh_token": user_token},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestLogout:
    async def test_logout_returns_204(self, client: AsyncClient, registered_user, user_headers):
        login = await client.post(
            "/api/v1/tokens",
            data={"username": "testuser@example.com", "password": "SecurePass1!"},
        )
        refresh_token = login.json()["refresh_token"]

        resp = await client.delete(
            "/api/v1/tokens",
            json={"refresh_token": refresh_token},
            headers=user_headers,
        )
        assert resp.status_code == 204

    async def test_refresh_after_logout_returns_401(
        self, client: AsyncClient, registered_user, user_headers
    ):
        login = await client.post(
            "/api/v1/tokens",
            data={"username": "testuser@example.com", "password": "SecurePass1!"},
        )
        tokens = login.json()
        refresh_token = tokens["refresh_token"]

        # Logout
        await client.delete(
            "/api/v1/tokens",
            json={"refresh_token": refresh_token},
            headers=user_headers,
        )

        # Attempt to refresh with revoked token
        resp = await client.put(
            "/api/v1/tokens",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401
