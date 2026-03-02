"""Unit tests for Celery click tasks."""
import hashlib
from unittest.mock import MagicMock, patch, call

import pytest

from app.tasks.click_tasks import _hash_ip, record_click


class TestHashIp:
    def test_returns_none_for_none_input(self):
        assert _hash_ip(None) is None

    def test_returns_none_for_empty_string(self):
        assert _hash_ip("") is None

    def test_returns_sha256_hex_digest(self):
        ip = "192.168.1.1"
        expected = hashlib.sha256(ip.encode()).hexdigest()
        assert _hash_ip(ip) == expected

    def test_different_ips_produce_different_hashes(self):
        hash1 = _hash_ip("1.1.1.1")
        hash2 = _hash_ip("8.8.8.8")
        assert hash1 != hash2

    def test_same_ip_produces_same_hash(self):
        assert _hash_ip("10.0.0.1") == _hash_ip("10.0.0.1")

    def test_hash_is_64_chars(self):
        result = _hash_ip("127.0.0.1")
        assert len(result) == 64


class TestRecordClickTask:
    def test_records_click_successfully(self):
        mock_link = MagicMock()
        mock_link.id = 42

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_link

        with patch("app.tasks.click_tasks.SyncSessionLocal", return_value=mock_db):
            record_click("abc123", "192.168.1.1", "Mozilla/5.0", "https://ref.com")

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        click_obj = mock_db.add.call_args[0][0]
        assert click_obj.link_id == 42
        assert click_obj.ip_hash == hashlib.sha256(b"192.168.1.1").hexdigest()
        assert click_obj.user_agent == "Mozilla/5.0"
        assert click_obj.referer == "https://ref.com"

    def test_skips_when_link_not_found(self):
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.tasks.click_tasks.SyncSessionLocal", return_value=mock_db):
            record_click("missing-alias", "1.1.1.1", None, None)

        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    def test_hashes_ip_before_storing(self):
        mock_link = MagicMock()
        mock_link.id = 1

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_link

        with patch("app.tasks.click_tasks.SyncSessionLocal", return_value=mock_db):
            record_click("abc", "10.0.0.1", None, None)

        click_obj = mock_db.add.call_args[0][0]
        assert click_obj.ip_hash != "10.0.0.1"  # raw IP must NOT be stored
        assert click_obj.ip_hash == hashlib.sha256(b"10.0.0.1").hexdigest()

    def test_stores_none_ip_when_no_ip(self):
        mock_link = MagicMock()
        mock_link.id = 1

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_link

        with patch("app.tasks.click_tasks.SyncSessionLocal", return_value=mock_db):
            record_click("abc", None, None, None)

        click_obj = mock_db.add.call_args[0][0]
        assert click_obj.ip_hash is None

    def test_truncates_long_user_agent(self):
        mock_link = MagicMock()
        mock_link.id = 1

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_link

        long_ua = "A" * 1000

        with patch("app.tasks.click_tasks.SyncSessionLocal", return_value=mock_db):
            record_click("abc", None, long_ua, None)

        click_obj = mock_db.add.call_args[0][0]
        assert len(click_obj.user_agent) == 512

    def test_truncates_long_referer(self):
        mock_link = MagicMock()
        mock_link.id = 1

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_link

        long_ref = "B" * 5000

        with patch("app.tasks.click_tasks.SyncSessionLocal", return_value=mock_db):
            record_click("abc", None, None, long_ref)

        click_obj = mock_db.add.call_args[0][0]
        assert len(click_obj.referer) == 2048

    def test_retries_on_db_error(self):
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.execute.side_effect = Exception("DB down")

        # Patch retry to raise to stop the retry loop
        retry_exc = Exception("retry called")
        with (
            patch("app.tasks.click_tasks.SyncSessionLocal", return_value=mock_db),
            patch.object(record_click, "retry", side_effect=retry_exc),
        ):
            with pytest.raises(Exception):
                record_click("abc", "1.1.1.1", None, None)