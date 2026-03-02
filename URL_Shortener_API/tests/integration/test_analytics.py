import pytest
from httpx import AsyncClient

from app.repositories import click_repo


@pytest.mark.asyncio
class TestAnalytics:
    async def test_get_stats_returns_counts(
        self, client: AsyncClient, user_headers, db_session
    ):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com/stats-test"},
            headers=user_headers,
        )
        alias = create.json()["alias"]
        link_id = create.json()["id"]

        # Manually insert click records (bypasses Celery in tests)
        await click_repo.create(
            db_session, link_id=link_id, ip_hash="hash1", user_agent="test-agent", referer=None
        )
        await click_repo.create(
            db_session, link_id=link_id, ip_hash="hash2", user_agent="test-agent", referer=None
        )

        resp = await client.get(f"/api/v1/links/{alias}/stats", headers=user_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["alias"] == alias
        assert body["total_clicks"] == 2
        assert body["unique_ips"] == 2

    async def test_stats_other_users_link_returns_404(
        self, client: AsyncClient, user_headers
    ):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com/private"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        # Second user
        await client.post(
            "/api/v1/users",
            json={"email": "spy@example.com", "password": "SpyPass1!"},
        )
        login = await client.post(
            "/api/v1/tokens",
            data={"username": "spy@example.com", "password": "SpyPass1!"},
        )
        spy_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = await client.get(f"/api/v1/links/{alias}/stats", headers=spy_headers)
        assert resp.status_code == 404

    async def test_stats_unauthenticated_returns_401(self, client: AsyncClient, user_headers):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com/auth-check"},
            headers=user_headers,
        )
        alias = create.json()["alias"]
        resp = await client.get(f"/api/v1/links/{alias}/stats")
        assert resp.status_code == 401
