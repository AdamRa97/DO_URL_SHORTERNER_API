from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRedirect:
    async def test_redirect_valid_alias(self, client: AsyncClient, user_headers):
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://www.example.com/destination"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        resp = await client.get(f"/{alias}", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://www.example.com/destination"

    async def test_redirect_unknown_alias_returns_404(self, client: AsyncClient):
        resp = await client.get("/definitely-does-not-exist", follow_redirects=False)
        assert resp.status_code == 404

    async def test_redirect_expired_link_returns_404(
        self, client: AsyncClient, user_headers
    ):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        create = await client.post(
            "/api/v1/links",
            json={
                "original_url": "https://example.com/expired",
                "expires_at": past.isoformat(),
            },
            headers=user_headers,
        )
        alias = create.json()["alias"]

        resp = await client.get(f"/{alias}", follow_redirects=False)
        assert resp.status_code == 404

    async def test_redirect_uses_cache_on_second_request(
        self, client: AsyncClient, user_headers
    ):
        """Second request should still return 302 (served from Redis cache)."""
        create = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com/cached"},
            headers=user_headers,
        )
        alias = create.json()["alias"]

        resp1 = await client.get(f"/{alias}", follow_redirects=False)
        resp2 = await client.get(f"/{alias}", follow_redirects=False)

        assert resp1.status_code == 302
        assert resp2.status_code == 302
        assert resp1.headers["location"] == resp2.headers["location"]
