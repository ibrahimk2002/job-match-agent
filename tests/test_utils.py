import pytest
import os
import sys
import hashlib
from unittest.mock import patch, MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))
sys.path.insert(0, project_root)

from utils.utils import hash_url, setup_logging, log_info, log_error


class TestHashUrl:
    """Test suite for hash_url function."""

    def test_hash_url_consistency(self):
        """Test that hash_url returns consistent results."""
        url = "https://example.com/job/123"
        hash1 = hash_url(url)
        hash2 = hash_url(url)
        assert hash1 == hash2

    def test_hash_url_format(self):
        """Test that hash_url returns valid SHA256 hex string."""
        url = "https://example.com/job/123"
        result = hash_url(url)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_url_different_urls(self):
        """Test that different URLs produce different hashes."""
        url1 = "https://example.com/job/1"
        url2 = "https://example.com/job/2"
        assert hash_url(url1) != hash_url(url2)

    def test_hash_url_case_sensitive(self):
        """Test that hash_url is case-sensitive."""
        url_lower = "https://example.com/job/123"
        url_upper = "https://example.com/job/123".upper()
        assert hash_url(url_lower) != hash_url(url_upper)

    def test_hash_url_empty_string(self):
        """Test hash_url with empty string."""
        result = hash_url("")
        expected = hashlib.sha256("".encode()).hexdigest()
        assert result == expected

    def test_hash_url_special_characters(self):
        """Test hash_url with special characters."""
        url = "https://example.com/job?id=123&filter=python&salary=100k"
        result = hash_url(url)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_url_long_url(self):
        """Test hash_url with very long URL."""
        url = "https://example.com/" + "a" * 1000 + "/job"
        result = hash_url(url)
        assert isinstance(result, str)
        assert len(result) == 64


class TestLogging:
    """Test suite for logging utility functions."""

    def test_setup_logging_creates_basic_config(self, temp_logs_dir, monkeypatch):
        """Test that setup_logging configures logging without raising."""
        monkeypatch.setattr("logging.basicConfig", lambda **kwargs: None)
        setup_logging()

    def test_log_info(self, temp_logs_dir, monkeypatch):
        """Test log_info calls logging.info with the supplied message."""
        mock_logger = MagicMock()
        with patch("utils.utils.logging") as mock_logging:
            mock_logging.info = mock_logger
            log_info("Test message")
            mock_logging.info.assert_called_once_with("Test message")

    def test_log_error(self, temp_logs_dir, monkeypatch):
        """Test log_error calls logging.error with the supplied message."""
        mock_logger = MagicMock()
        with patch("utils.utils.logging") as mock_logging:
            mock_logging.error = mock_logger
            log_error("Test error")
            mock_logging.error.assert_called_once_with("Test error")

    def test_log_info_accepts_string(self):
        """Test that log_info accepts string messages without raising."""
        with patch("utils.utils.logging"):
            log_info("This is a test message")

    def test_log_error_accepts_string(self):
        """Test that log_error accepts string messages without raising."""
        with patch("utils.utils.logging"):
            log_error("This is an error message")
