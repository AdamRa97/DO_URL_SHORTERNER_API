"""Unit tests for custom exception classes and FastAPI exception handlers."""
import pytest
from fastapi import Request
from unittest.mock import MagicMock

from app.core.exceptions import (
    AliasConflictError,
    AliasValidationError,
    AuthenticationError,
    AuthorizationError,
    LinkNotFoundError,
    alias_conflict_handler,
    alias_validation_error_handler,
    authentication_error_handler,
    authorization_error_handler,
    link_not_found_handler,
)


def _mock_request():
    return MagicMock(spec=Request)


# ---------------------------------------------------------------------------
# Exception class hierarchy
# ---------------------------------------------------------------------------

class TestExceptionClasses:
    def test_alias_conflict_error_is_exception(self):
        exc = AliasConflictError("taken")
        assert isinstance(exc, Exception)
        assert str(exc) == "taken"

    def test_link_not_found_error_is_exception(self):
        assert isinstance(LinkNotFoundError(), Exception)

    def test_authentication_error_is_exception(self):
        assert isinstance(AuthenticationError(), Exception)

    def test_authorization_error_is_exception(self):
        assert isinstance(AuthorizationError(), Exception)

    def test_alias_validation_error_is_value_error(self):
        exc = AliasValidationError("bad alias")
        assert isinstance(exc, ValueError)
        assert str(exc) == "bad alias"


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

class TestAuthenticationErrorHandler:
    async def test_returns_401_with_www_authenticate_header(self):
        request = _mock_request()
        exc = AuthenticationError()

        response = await authentication_error_handler(request, exc)

        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"

    async def test_body_contains_generic_message(self):
        import json
        request = _mock_request()
        response = await authentication_error_handler(request, AuthenticationError())
        body = json.loads(response.body)
        assert "detail" in body
        assert body["detail"] == "Invalid credentials"


class TestAuthorizationErrorHandler:
    async def test_returns_403(self):
        request = _mock_request()
        response = await authorization_error_handler(request, AuthorizationError())
        assert response.status_code == 403

    async def test_body_contains_permissions_message(self):
        import json
        request = _mock_request()
        response = await authorization_error_handler(request, AuthorizationError())
        body = json.loads(response.body)
        assert body["detail"] == "Insufficient permissions"


class TestLinkNotFoundHandler:
    async def test_returns_404(self):
        request = _mock_request()
        response = await link_not_found_handler(request, LinkNotFoundError())
        assert response.status_code == 404

    async def test_body_contains_not_found_message(self):
        import json
        request = _mock_request()
        response = await link_not_found_handler(request, LinkNotFoundError())
        body = json.loads(response.body)
        assert body["detail"] == "Not found"


class TestAliasConflictHandler:
    async def test_returns_409(self):
        request = _mock_request()
        response = await alias_conflict_handler(request, AliasConflictError("taken"))
        assert response.status_code == 409

    async def test_body_contains_conflict_message(self):
        import json
        request = _mock_request()
        response = await alias_conflict_handler(request, AliasConflictError("taken"))
        body = json.loads(response.body)
        assert "already taken" in body["detail"]


class TestAliasValidationErrorHandler:
    async def test_returns_422(self):
        request = _mock_request()
        response = await alias_validation_error_handler(request, AliasValidationError("bad"))
        assert response.status_code == 422

    async def test_body_contains_error_message(self):
        import json
        request = _mock_request()
        response = await alias_validation_error_handler(request, AliasValidationError("Too short"))
        body = json.loads(response.body)
        assert body["detail"] == "Too short"