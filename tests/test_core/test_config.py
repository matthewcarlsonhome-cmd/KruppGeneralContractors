"""Tests for kruppai.core.config."""

import os
from pathlib import Path

import pytest

from kruppai.core.config import Settings


class TestSettings:
    def test_default_settings_load(self) -> None:
        """Settings instantiate with defaults, no env vars needed."""
        settings = Settings(_env_file=None)
        assert settings.default_model == "claude-sonnet-4-5-20250929"
        assert settings.opus_model == "claude-opus-4-6"
        assert settings.daily_cost_limit_cents == 5000
        assert settings.monthly_cost_limit_cents == 30000
        assert settings.weather_enabled is True

    def test_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting KRUPPAI_OUTPUT_DIR overrides default."""
        test_dir = tmp_path / "custom_output"
        monkeypatch.setenv("KRUPPAI_OUTPUT_DIR", str(test_dir))
        settings = Settings(_env_file=None)
        assert settings.output_dir == test_dir

    def test_ensure_directories(self, tmp_path: Path) -> None:
        """ensure_directories() creates paths."""
        settings = Settings(
            db_path=tmp_path / "sub" / "test.db",
            output_dir=tmp_path / "output",
            _env_file=None,
        )
        settings.ensure_directories()
        assert (tmp_path / "sub").is_dir()
        assert (tmp_path / "output").is_dir()

    def test_api_key_from_anthropic_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reads ANTHROPIC_API_KEY environment variable."""
        monkeypatch.setenv("KRUPPAI_ANTHROPIC_API_KEY", "sk-ant-test-123")
        settings = Settings(_env_file=None)
        assert settings.anthropic_api_key == "sk-ant-test-123"

    def test_path_expansion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Paths with ~ are expanded."""
        monkeypatch.setenv("KRUPPAI_DB_PATH", "~/test_kruppai/db.sqlite")
        settings = Settings(_env_file=None)
        assert "~" not in str(settings.db_path)
        assert str(settings.db_path).startswith("/")
