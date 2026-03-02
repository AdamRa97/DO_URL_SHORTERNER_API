import pytest
from httpx import AsyncClient

from app.models.user import RoleEnum
from app.core.security import hash_password
from app.repositories import user_repo


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/users",
            json={"email": "new@example.com", "password": "SecurePass1!"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@example.com"
        assert body["role"] == "user"
        assert "id" in body

    async def test_register_duplicate_email_returns_400(self, client: AsyncClient):
        await client.post(
            "/api/v1/users",
            json={"email": "dup@example.com", "password": "SecurePass1!"},
        )
        resp = await client.post(
            "/api/v1/users",
            json={"email": "dup@example.com", "password": "SecurePass1!"},
        )
        assert resp.status_code == 400
        # Generic error — does not confirm the email already exists
        assert resp.json()["detail"] == "Registration failed. Please try again."

    async def test_register_short_password_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/users",
            json={"email": "weak@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/users",
            json={"email": "not-an-email", "password": "SecurePass1!"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestAdminUserOps:
    @pytest.fixture
    async def admin_headers(self, client: AsyncClient, db_session):
        """Create an admin user and return auth headers."""
        hashed = hash_password("AdminPass1!")
        admin = await user_repo.create(
            db_session,
            email="admin@example.com",
            hashed_password=hashed,
            role=RoleEnum.admin,
        )
        resp = await client.post(
            "/api/v1/tokens",
            data={"username": "admin@example.com", "password": "AdminPass1!"},
        )
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_list_users_as_admin(
        self, client: AsyncClient, registered_user, admin_headers
    ):
        resp = await client.get("/api/v1/users", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body

    async def test_list_users_as_non_admin_returns_403(
        self, client: AsyncClient, user_headers
    ):
        resp = await client.get("/api/v1/users", headers=user_headers)
        assert resp.status_code == 403

    async def test_get_user_as_admin(
        self, client: AsyncClient, registered_user, admin_headers
    ):
        user_id = registered_user["id"]
        resp = await client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == user_id

    async def test_delete_user_as_admin(
        self, client: AsyncClient, db_session, admin_headers
    ):
        # Create a user to delete
        hashed = hash_password("TempPass1!")
        user = await user_repo.create(
            db_session,
            email="todelete@example.com",
            hashed_password=hashed,
        )
        resp = await client.delete(f"/api/v1/users/{user.id}", headers=admin_headers)
        assert resp.status_code == 204

    async def test_delete_nonexistent_user_returns_404(
        self, client: AsyncClient, admin_headers
    ):
        resp = await client.delete("/api/v1/users/999999", headers=admin_headers)
        assert resp.status_code == 404
