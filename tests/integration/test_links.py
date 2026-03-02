import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCreateLink:
    async def test_create_link_success(self, client: AsyncClient, user_headers):
        resp = await client.post(
            "/api/v1/links",
            json={"original_url": "https://www.example.com/very/long/path"},
            headers=user_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "alias" in body
        assert body["original_url"] == "https://www.example.com/very/long/path"

    async def test_same_url_twice_gets_different_aliases(
        self, client: AsyncClient, user_headers
    ):
        url = "https://www.example.com/same-url"
        resp1 = await client.post(
            "/api/v1/links", json={"original_url": url}, headers=user_headers
        )
        resp2 = await client.post(
            "/api/v1/links", json={"original_url": url}, headers=user_headers
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["alias"] != resp2.json()["alias"]

    async def test_create_with_custom_alias(self, client: AsyncClient, user_headers):
        resp = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com", "custom_alias": "my-link"},
            headers=user_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["alias"] == "my-link"

    async def test_duplicate_custom_alias_returns_409(
        self, client: AsyncClient, user_headers
    ):
        await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com", "custom_alias": "clash"},
            headers=user_headers,
        )
        resp = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com/2", "custom_alias": "clash"},
            headers=user_headers,
        )
        assert resp.status_code == 409

    async def test_invalid_url_returns_422(self, client: AsyncClient, user_headers):
        resp = await client.post(
            "/api/v1/links",
            json={"original_url": "not-a-valid-url"},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_reserved_alias_returns_422(self, client: AsyncClient, user_headers):
        resp = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com", "custom_alias": "api"},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestGetLink:
    async def test_get_own_link(self, client: AsyncClient, user_headers):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        resp = await client.get(f"/api/v1/links/{alias}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["alias"] == alias

    async def test_other_users_link_returns_404(
        self, client: AsyncClient, user_headers, db_session
    ):
        """A second user should get 404 (not 403) for another user's link."""
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        # Register and log in a second user
        await client.post(
            "/api/v1/users",
            json={"email": "other@example.com", "password": "OtherPass1!"},
        )
        login = await client.post(
            "/api/v1/tokens",
            data={"username": "other@example.com", "password": "OtherPass1!"},
        )
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = await client.get(f"/api/v1/links/{alias}", headers=other_headers)
        assert resp.status_code == 404

    async def test_nonexistent_alias_returns_404(self, client: AsyncClient, user_headers):
        resp = await client.get("/api/v1/links/doesnotexist", headers=user_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateLink:
    async def test_update_original_url(self, client: AsyncClient, user_headers):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com/old"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        resp = await client.put(
            f"/api/v1/links/{alias}",
            json={"original_url": "https://example.com/new"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["original_url"] == "https://example.com/new"


@pytest.mark.asyncio
class TestDeleteLink:
    async def test_delete_link(self, client: AsyncClient, user_headers):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        resp = await client.delete(f"/api/v1/links/{alias}", headers=user_headers)
        assert resp.status_code == 204

    async def test_get_after_delete_returns_404(self, client: AsyncClient, user_headers):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        await client.delete(f"/api/v1/links/{alias}", headers=user_headers)
        resp = await client.get(f"/api/v1/links/{alias}", headers=user_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestListLinks:
    async def test_list_own_links_paginated(self, client: AsyncClient, user_headers):
        for i in range(3):
            await client.post(
                "/api/v1/links",
                json={"original_url": f"https://example.com/{i}"},
                headers=user_headers,
            )

        resp = await client.get(
            "/api/v1/links?limit=2&offset=0", headers=user_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] >= 3
