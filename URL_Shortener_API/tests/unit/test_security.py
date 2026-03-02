import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPassword:
    def test_hash_is_not_plain(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"

    def test_verify_correct_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("correct-horse", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("wrong-password", hashed) is False

    def test_same_password_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token(user_id=42, role="user")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "user"
        assert payload["type"] == "access"

    def test_admin_role_embedded(self):
        token = create_access_token(user_id=1, role="admin")
        payload = decode_token(token)
        assert payload["role"] == "admin"

    def test_tampered_signature_raises(self):
        token = create_access_token(user_id=1, role="user")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_garbage_token_raises(self):
        with pytest.raises(JWTError):
            decode_token("not.a.token")


class TestRefreshToken:
    def test_create_returns_token_and_jti(self):
        token, jti = create_refresh_token()
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert len(jti) == 36  # UUID4 format

    def test_decode_refresh_token(self):
        token, jti = create_refresh_token()
        payload = decode_token(token)
        assert payload["jti"] == jti
        assert payload["type"] == "refresh"

    def test_access_token_cannot_be_used_as_refresh(self):
        access = create_access_token(user_id=1, role="user")
        payload = decode_token(access)
        assert payload["type"] == "access"  # not "refresh"

    def test_refresh_token_cannot_be_used_as_access(self):
        refresh, _ = create_refresh_token()
        payload = decode_token(refresh)
        assert payload["type"] == "refresh"  # not "access"
