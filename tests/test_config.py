import pytest
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))
sys.path.insert(0, project_root)

from src.utils.config import Config


class TestConfig:
    """Validates that Config correctly reads and validates API keys from environment variables."""

    def test_valid_keys_are_stored_as_attributes(self, monkeypatch):
        """Both keys present: Config instantiates and exposes their values."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-abc")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key-xyz")
        cfg = Config()
        assert cfg.OPENAI_API_KEY == "test-openai-key-abc", "OPENAI_API_KEY not stored correctly"
        assert cfg.FIRECRAWL_API_KEY == "test-firecrawl-key-xyz", "FIRECRAWL_API_KEY not stored correctly"

    def test_key_attributes_are_strings(self, monkeypatch):
        """Config attributes must be plain str instances."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-abc")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key-xyz")
        cfg = Config()
        assert isinstance(cfg.OPENAI_API_KEY, str)
        assert isinstance(cfg.FIRECRAWL_API_KEY, str)

    def test_missing_openai_key_raises_runtime_error(self, monkeypatch):
        """Missing OPENAI_API_KEY must raise RuntimeError with descriptive message."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key-xyz")
        with pytest.raises(RuntimeError, match="Missing OPENAI_API_KEY"):
            Config()

    def test_missing_firecrawl_key_raises_runtime_error(self, monkeypatch):
        """Missing FIRECRAWL_API_KEY must raise RuntimeError with descriptive message."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-abc")
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="Missing FIRECRAWL_API_KEY"):
            Config()

    def test_missing_both_keys_raises_for_openai_first(self, monkeypatch):
        """When both keys are absent, OPENAI_API_KEY error is raised first."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="Missing OPENAI_API_KEY"):
            Config()

    def test_empty_openai_key_raises_runtime_error(self, monkeypatch):
        """An empty string for OPENAI_API_KEY is treated as missing."""
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key-xyz")
        with pytest.raises(RuntimeError, match="Missing OPENAI_API_KEY"):
            Config()

    def test_empty_firecrawl_key_raises_runtime_error(self, monkeypatch):
        """An empty string for FIRECRAWL_API_KEY is treated as missing."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-abc")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "")
        with pytest.raises(RuntimeError, match="Missing FIRECRAWL_API_KEY"):
            Config()
