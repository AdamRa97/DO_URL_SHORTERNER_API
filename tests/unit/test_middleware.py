"""Unit tests for RequestIDMiddleware."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient
from fastapi import FastAPI

from app.middleware.request_id import RequestIDMiddleware


def _make_app_with_middleware():
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


class TestRequestIDMiddleware:
    def test_generates_request_id_when_header_absent(self):
        app = _make_app_with_middleware()
        client = TestClient(app)

        response = client.get("/ping")

        assert "x-request-id" in response.headers
        # Should be a valid UUID
        req_id = response.headers["x-request-id"]
        uuid.UUID(req_id)  # raises ValueError if not valid UUID

    def test_echoes_provided_request_id(self):
        app = _make_app_with_middleware()
        client = TestClient(app)
        my_id = "my-custom-request-id"

        response = client.get("/ping", headers={"X-Request-ID": my_id})

        assert response.headers["x-request-id"] == my_id

    def test_different_requests_get_different_ids(self):
        app = _make_app_with_middleware()
        client = TestClient(app)

        r1 = client.get("/ping")
        r2 = client.get("/ping")

        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    def test_request_id_present_in_response_headers(self):
        app = _make_app_with_middleware()
        client = TestClient(app)

        response = client.get("/ping")

        assert response.status_code == 200
        assert "x-request-id" in response.headers